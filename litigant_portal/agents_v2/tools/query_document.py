import litellm

from litigant_portal.agents_v2.base import Field, Tool, ToolOutput
from litigant_portal.settings import CHAT_MODEL

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
        from litigant_portal.app.services.attachments import (
            content_part,
            reader_limit_error,
        )

        thread = ChatThread.objects.get(id=thread_id)
        upload = UserUpload.objects.filter(
            id=self.upload_id, identity=thread.identity
        ).first()
        if upload is None:
            return ToolOutput(
                result=(
                    f"Error: no attached file with "
                    f"upload_id={self.upload_id}."
                )
            )

        with upload.file.open("rb") as f:
            data = f.read()

        too_large = reader_limit_error(upload, data)
        if too_large:
            return ToolOutput(
                result=(
                    f"Error: {upload.name} is too large to process "
                    f"({too_large})."
                )
            )

        part = content_part(upload=upload, data=data, model=CHAT_MODEL)
        if part is None:
            return ToolOutput(
                result=(
                    f"Error: {upload.name} ({upload.content_type}) "
                    f"can't be read by the document reader."
                )
            )

        answer, cost = self.ask(upload.name, part)
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

    def ask(self, name: str, part: dict) -> tuple[str, float]:
        """One reader call; returns the answer and what it cost."""
        response = litellm.completion(
            model=CHAT_MODEL,
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
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0
        return (response.choices[0].message.content or "").strip(), cost
