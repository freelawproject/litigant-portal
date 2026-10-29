import litellm
from django.conf import settings

from litigant_portal.agents.base import Field, Tool, ToolOutput
from litigant_portal.app.selectors.bedrock import bedrock_model_failed
from lp_agent.adapters.bedrock_models import ResolvedBedrockModel

READER_SYSTEM_PROMPT = (
    "You are a document analyzer. Answer the request using only the "
    "provided file. Be concise and factual, and quote exact text when it "
    "helps. If the file does not contain the requested information, say "
    "so plainly."
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
        from litigant_portal.app.selectors.site import site_get_model_target
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

        required = frozenset(
            {"text", "image"} if part.get("type") == "image_url" else {"text"}
        )
        model = site_get_model_target(role="assistant", required=required)
        try:
            answer, cost = self.ask(upload.name, part, model)
        except Exception as error:
            bedrock_model_failed(error)
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
        """One reader call; returns the answer and what it cost."""
        response = litellm.completion(
            **model.invocation_options(),
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
        except Exception:
            cost = 0.0
        return (response.choices[0].message.content or "").strip(), cost
