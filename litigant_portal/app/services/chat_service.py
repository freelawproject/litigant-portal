"""Chat service for managing conversations and AI responses."""

import json
import logging
from collections.abc import Iterator
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest, StreamingHttpResponse

from litigant_portal.agents import agent_registry

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing a chat conversation."""

    # Temporary topic → default jurisdiction map. Replaced when
    # #179 (court-configurable context) lands and the deep-link / topic-card
    # carries jurisdiction through the request.
    _DEFAULT_JURISDICTION_FOR_TOPIC: dict[str, str] = {
        "eviction": "il",
        "adult_name_change": "nd",
    }

    def __init__(
        self,
        request: HttpRequest,
        session_id: str | UUID | None = None,
        agent_name: str | None = None,
        topic: str | None = None,
        court: str | None = None,
    ):
        self.request = request
        agent_class = agent_registry[agent_name or settings.DEFAULT_CHAT_AGENT]
        agent_kwargs = {}
        if topic:
            agent_kwargs["topic"] = topic
            # Jurisdiction default (for session storage + backward-compat
            # composition on resume). Replaced when #179 carries jurisdiction
            # through the request.
            jurisdiction = self._DEFAULT_JURISDICTION_FOR_TOPIC.get(topic)
            if jurisdiction:
                agent_kwargs["jurisdiction"] = jurisdiction
        if court:
            # Explicit court (from deep-link) wins over the jurisdiction
            # default in build_system_prompt (explicit ``court`` > mapped
            # from ``jurisdiction``). Session still stores jurisdiction for
            # resume-time composition.
            agent_kwargs["court"] = court
        # Phase is derived from session state inside from_session_id for
        # existing sessions; new sessions default to "triage" there.
        self.agent = agent_class.from_session_id(
            request.identity, session_id, **agent_kwargs
        )

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
