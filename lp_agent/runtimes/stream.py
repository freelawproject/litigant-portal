"""
Encode async run events for synchronous streaming hosts.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from typing import Self

from lp_agent.errors import AgentError, AgentValidationError
from lp_agent.interfaces import RunHandle
from lp_agent.types import RunEvent

logger = logging.getLogger(__name__)


class EventStream(Iterator[str]):
    """
    Own one agent and event loop until exhaustion or explicit closure.

    Call close() when stopping early, or use this iterator as a context manager.
    Even closure before the first iteration closes the owned agent.
    """

    def __init__(
        self,
        *,
        submit: Callable[[], Awaitable[RunHandle]],
        close_agent: Callable[[], Awaitable[None]],
    ) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise AgentValidationError("Use run() from an async caller.")
        self._submit = submit
        self._close_agent = close_agent
        self._runner = asyncio.Runner()
        self._events: AsyncGenerator[RunEvent] | None = None
        self._closed = False

    def __next__(self) -> str:
        if self._closed:
            raise StopIteration
        try:
            if self._events is None:
                run = self._runner.run(self._submit())
                self._events = run.events()
            event = self._runner.run(anext(self._events))
            return event.model_dump_json() + "\n"
        except StopAsyncIteration:
            self.close()
            raise StopIteration from None
        except Exception as exc:
            message = "Unable to run the agent. Please try again."
            if isinstance(exc, AgentError):
                message = str(exc)
            else:
                logger.warning("Agent event stream failed.")
            try:
                self.close()
            except Exception:
                logger.warning("Agent event stream cleanup failed.")
            return json.dumps({"error": message}) + "\n"

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._events is not None:
                self._runner.run(self._events.aclose())
        finally:
            try:
                self._runner.run(self._close_agent())
            finally:
                self._runner.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
