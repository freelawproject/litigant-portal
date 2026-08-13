"""Tools for the simulated litigant actor.

App imports stay inside functions — ``litigant_portal.app.models`` imports
this package's message schema, so module-level app imports would be
circular.
"""

from litigant_portal.agents.base import Field, Tool, ToolOutput


class AttachUpload(Tool):
    """Attach files from your documents to your next message.

    Use this when the assistant asks for a document you actually have in
    YOUR DOCUMENTS. Call it once, listing every file the next message
    should carry, then mention in your message that you're sending it.
    Never attach a document that isn't in your list.
    """

    upload_ids: list[str] = Field(
        description="upload_id values from YOUR DOCUMENTS to attach"
    )

    tool_call_template = False
    tool_result_template = False

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.models import ChatThread
        from litigant_portal.app.selectors.upload import user_upload_list

        thread = ChatThread.objects.get(id=thread_id)
        uploads = {
            str(upload.id): upload
            for upload in user_upload_list(identity=thread.identity)
        }
        unknown = [i for i in self.upload_ids if i not in uploads]
        if unknown:
            return ToolOutput(
                result=(
                    "Error: you have no document with upload_id "
                    f"{', '.join(unknown)}. Your documents are listed in "
                    "your instructions; only attach those."
                )
            )
        ids = list(dict.fromkeys(self.upload_ids))
        names = [uploads[i].name for i in ids]
        return ToolOutput(
            result=(
                f"Attached to your next message: {', '.join(names)}. "
                "Now write that message."
            ),
            # The run loop reads these off the stream to forward the
            # attachments onto the assistant-side message.
            render_data={"upload_ids": ids, "names": names},
        )


class EndConversation(Tool):
    """End the conversation.

    Use this once your needs are met, or the conversation has genuinely
    run its course (you said goodbye, or you are stuck and giving up).
    Send your final goodbye message in the same turn you call this.
    """

    reason: str = Field(
        description="One sentence on why the conversation is over"
    )

    tool_call_template = False
    tool_result_template = False

    def __call__(self, *, thread_id) -> ToolOutput:
        return ToolOutput(
            result=(
                "Understood, the conversation will end after this message."
            ),
            render_data={"reason": self.reason},
        )
