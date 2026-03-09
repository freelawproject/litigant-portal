"""Chat service for managing conversations and AI responses."""

import json
import logging
from collections.abc import Iterator
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest, StreamingHttpResponse

from chat.agents import agent_registry

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing a chat conversation."""

    def __init__(
        self,
        request: HttpRequest,
        session_id: str | UUID | None = None,
        agent_name: str | None = None,
    ):
        self.request = request
        agent_class = agent_registry[agent_name or settings.DEFAULT_CHAT_AGENT]
        self.agent = agent_class.from_session_id(request, session_id)

    def stream(self, user_message: str) -> StreamingHttpResponse:
        """Add user message and stream the AI response."""

        def event_stream() -> Iterator[str]:
            session_id = self.agent.session.id if self.agent.session else None
            yield f"data: {json.dumps({'type': 'session', 'session_id': str(session_id)})}\n\n"

            try:
                for event in self.agent.stream_run(user_message):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                logger.exception("Error streaming response")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
