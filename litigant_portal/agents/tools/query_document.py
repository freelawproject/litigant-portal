import logging

import litellm
from django.conf import settings

from litigant_portal.agents.base import Field, Tool, ToolOutput
from litigant_portal.agents.bedrock import ResolvedBedrockModel

logger = logging.getLogger(__name__)

READER_SYSTEM_PROMPT = (
    "You are a document analyzer. Answer the request using only the "
    "provided file. Be concise and factual, and quote exact text when it "
    "helps. If the file does not contain the requested information, say "
    "so plainly."
)

READER_TRUNCATION_NOTICE = (
    "This answer is incomplete because the document reader reached its "
    "response limit. Ask a more specific question for the missing details."
)


class QueryDocument(Tool):
    """Read a file the user attached and answer a request about it.

    Use this for any attached file that is not included inline in the
    conversation — its attachment note says to use this tool — or to
    re-read an earlier attachment. The request can ask for a summary,
    specific facts, exact quotes, or anything else in the file.
    """

    upload_id: str = Field(description="The upload_id of the attached file")
    request: str = Field(
        description="What to find, extract, or summarize from the file"
    )

    tool_call_template = "tools/query_document_call.html"
    tool_result_template = "tools/query_document_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.models import ChatThread, UserUpload
        from litigant_portal.app.selectors.site import (
            site_get_reader_model_target,
        )
        from litigant_portal.app.services.bedrock import (
            bedrock_catalog_invalidate_on_error,
        )
        from litigant_portal.app.services.upload import (
            user_upload_content_part,
            user_upload_reader_limit_error,
        )

        thread = ChatThread.objects.get(id=thread_id)
        upload = UserUpload.objects.filter(
            id=self.upload_id, identity=thread.identity
        ).first()
        if upload is None:
            return ToolOutput(
                result=(
                    f"Error: no attached file with upload_id={self.upload_id}."
                )
            )

        with upload.file.open("rb") as f:
            data = f.read()

        too_large = user_upload_reader_limit_error(upload=upload, data=data)
        if too_large:
            return ToolOutput(
                result=(
                    f"Error: {upload.name} is too large to process "
                    f"({too_large})."
                )
            )

        part = user_upload_content_part(upload=upload, data=data)
        if part is None:
            return ToolOutput(
                result=(
                    f"Error: {upload.name} ({upload.content_type}) "
                    f"can't be read by the document reader."
                )
            )

        modality = {"image_url": "image", "file": "document"}.get(
            part.get("type"), "text"
        )
        required = frozenset({"text", modality})
        model = site_get_reader_model_target(required=required)
        try:
            answer, cost = self.ask(upload.name, part, model)
        except Exception as error:
            bedrock_catalog_invalidate_on_error(error)
            raise
        return ToolOutput(
            result=answer,
            cost=cost,
            render_data={
                "name": upload.name,
                "upload_id": str(upload.id),
                "request": self.request,
                "response": answer,
            },
        )

    def ask(
        self, name: str, part: dict, model: ResolvedBedrockModel
    ) -> tuple[str, float]:
        """
        Make one reader call and return the answer and its cost.
        """
        response = litellm.completion(
            **model.invocation_options(small_task=True),
            api_key=settings.BEDROCK_API_KEY,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": READER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f'File: "{name}"\n\nRequest: {self.request}',
                        },
                        part,
                    ],
                },
            ],
        )
        try:
            cost = model.completion_cost(response.usage)
        except Exception as error:
            logger.warning(
                "Document reader cost extraction failed (%s, model=%s)",
                type(error).__name__,
                model.model,
            )
            cost = 0.0
        choice = response.choices[0]
        answer = (choice.message.content or "").strip()
        if getattr(choice, "finish_reason", None) == "length":
            logger.warning(
                "Document reader output truncated (model=%s, upload_id=%s)",
                model.model,
                self.upload_id,
            )
            answer = f"{READER_TRUNCATION_NOTICE}\n\n{answer}".strip()
        return answer, cost
