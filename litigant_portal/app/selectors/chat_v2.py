from django.db.models import QuerySet

from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity


def chat_thread_list(*, identity: UserIdentity) -> QuerySet[ChatThread]:
    """Chat threads for an identity, most recently updated first."""
    return ChatThread.objects.filter(identity=identity).order_by("-updated_at")


def chat_thread_get(*, identity: UserIdentity, thread_id) -> ChatThread:
    """A single thread owned by the identity (raises ChatThread.DoesNotExist)."""
    return ChatThread.objects.get(id=thread_id, identity=identity)


def chat_message_list(*, thread: ChatThread) -> QuerySet[ChatMessage]:
    """Messages in a thread, oldest first."""
    return thread.messages.order_by("created_at")
