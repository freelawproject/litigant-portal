import json
import logging
from collections.abc import Iterator

from django.conf import settings
from django.http import HttpRequest, StreamingHttpResponse

from chat.models import ChatSession, Message
from chat.providers.base import ChatMessage
from chat.providers.factory import get_provider

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat conversations and AI responses."""

    def get_or_create_session(self, request: HttpRequest) -> ChatSession:
        """
        Get or create a chat session for the current request.

        Uses authenticated user if available, otherwise falls back to
        Django session key for anonymous users.

        Args:
            request: The HTTP request.

        Returns:
            The chat session for this user/session.
        """
        if request.user.is_authenticated:
            session, _ = ChatSession.objects.get_or_create(user=request.user)
        else:
            # Ensure session exists for anonymous users
            if not request.session.session_key:
                request.session.create()
            session, _ = ChatSession.objects.get_or_create(
                session_key=request.session.session_key
            )
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """
        Get a chat session by ID.

        Args:
            session_id: The session UUID.

        Returns:
            The chat session or None if not found.
        """
        try:
            return ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return None

    def add_user_message(self, session: ChatSession, content: str) -> Message:
        """
        Add a user message to the session.

        Args:
            session: The chat session.
            content: The message content.

        Returns:
            The created message.
        """
        return Message.objects.create(
            session=session,
            role=Message.Role.USER,
            content=content,
        )

    def build_message_history(self, session: ChatSession) -> list[ChatMessage]:
        """
        Build the message history for the LLM.

        Args:
            session: The chat session.

        Returns:
            List of ChatMessage objects for the provider.
        """
        messages = session.messages.all().order_by("created_at")
        return [ChatMessage(role=m.role, content=m.content) for m in messages]

    def stream_response(self, session: ChatSession) -> StreamingHttpResponse:
        """
        Generate a streaming SSE response for the chat.

        Args:
            session: The chat session to respond to.

        Returns:
            A StreamingHttpResponse with SSE content.
        """

        def event_stream() -> Iterator[str]:
            full_response: list[str] = []

            try:
                provider = get_provider()
                messages = self.build_message_history(session)

                # TODO: Add RAG context retrieval here
                context = None

                for token in provider.stream_response(messages, context):
                    full_response.append(token)
                    # Send token as SSE event
                    data = json.dumps({"token": token})
                    yield f"data: {data}\n\n"

                # Save the complete assistant response
                Message.objects.create(
                    session=session,
                    role=Message.Role.ASSISTANT,
                    content="".join(full_response),
                )

                # Send completion signal
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Error streaming response: {e}")
                error_msg = (
                    "I apologize, but I encountered an error. "
                    "Please try again or use the search feature."
                )
                # Save error as assistant response
                Message.objects.create(
                    session=session,
                    role=Message.Role.ASSISTANT,
                    content=error_msg,
                )
                data = json.dumps({"error": str(e), "message": error_msg})
                yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    def is_available(self) -> bool:
        """
        Check if the chat service is available.

        Returns:
            True if chat is enabled and provider is healthy.
        """
        if not settings.CHAT_ENABLED:
            return False

        try:
            provider = get_provider()
            return provider.health_check()
        except Exception as e:
            logger.warning(f"Chat service unavailable: {e}")
            return False

    def generate_summary(self, messages: list[dict]) -> str | None:
        """
        Generate a summary of a conversation.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            A Q&A summary of the conversation, or None on error.
        """
        if not messages:
            return None

        try:
            provider = get_provider()

            # Build conversation text
            conversation_text = "\n".join(
                f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
                for msg in messages
                if msg.get("content")
            )

            # Simple system prompt for summarization (not the chat prompt)
            system_prompt = "You summarize conversations. Be concise."

            user_prompt = f"""Summarize this Q&A exchange.

Format:
Q: [user's question]
A: [key points from the answer - specific details like names, numbers, addresses]

If the user message is just confirming document info (like "yes" or "looks correct"), respond: "No user questions asked."

Conversation:
{conversation_text}"""

            # Use provider's client directly to avoid chat system prompt
            formatted_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = provider.client.chat.completions.create(
                model=provider.model,
                max_tokens=200,
                messages=formatted_messages,
                temperature=0.3,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None


# Singleton instance
chat_service = ChatService()
