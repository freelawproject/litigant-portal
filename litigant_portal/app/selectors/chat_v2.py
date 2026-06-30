from django.db.models import QuerySet

from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity


def chat_thread_list(*, identity: UserIdentity) -> QuerySet[ChatThread]:
    """Chat threads for an identity, most recently updated first."""
    return ChatThread.objects.filter(identity=identity).order_by("-updated_at")


def chat_thread_get(*, identity: UserIdentity, thread_id) -> ChatThread:
    """A single thread owned by the identity (raises ChatThread.DoesNotExist)."""
    return ChatThread.objects.get(id=thread_id, identity=identity)


def chat_message_list(*, thread: ChatThread) -> QuerySet[ChatMessage]:
    """All messages in a thread, oldest first (includes hidden)."""
    return thread.messages.order_by("created_at")


def chat_message_list_visible(*, thread: ChatThread) -> QuerySet[ChatMessage]:
    """Frontend-safe messages: the thread's messages minus hidden ones."""
    return chat_message_list(thread=thread).filter(hidden=False)
