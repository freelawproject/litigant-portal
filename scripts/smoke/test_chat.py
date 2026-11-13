import json
import time

import pytest
from playwright.sync_api import APIResponse, Page, Route

CHAT_PATH = "/chat/"
STREAM_PATH = "/api/agents/assistant/stream/"
CHAT_MESSAGE = "Hello"
# Unmeasured: timing a cold start needs a Bedrock token.
STREAM_TIMEOUT_SECONDS = 120
# The portal caches a failed Bedrock catalog discovery for 60 seconds.
DISCOVERY_FAILURE_CACHE_SECONDS = 60
POLL_INTERVAL_MS = 250


@pytest.mark.flaky(reruns=1, reruns_delay=DISCOVERY_FAILURE_CACHE_SECONDS + 5)
def test_chat_streams_reply(page: Page) -> None:
    stream_responses = proxy_stream_responses(page)
    page.goto(CHAT_PATH)
    send_chat_message(page, CHAT_MESSAGE)
    stream_response = wait_for_stream_response(page, stream_responses)
    check_content_delta_streamed(stream_response)


def proxy_stream_responses(page: Page) -> list[APIResponse]:
    stream_responses: list[APIResponse] = []

    # The client drops the request on a non-200, an error event or done. If
    # that beats the end of the response, the browser keeps no body to read,
    # so Playwright fetches the response itself and hands the page a copy.
    def proxy(route: Route) -> None:
        stream_response = route.fetch(timeout=STREAM_TIMEOUT_SECONDS * 1000)
        stream_responses.append(stream_response)
        route.fulfill(response=stream_response)

    page.route(f"**{STREAM_PATH}", proxy)
    return stream_responses


def send_chat_message(page: Page, message: str) -> None:
    page.get_by_role("textbox", name="Type your message...").fill(message)
    page.get_by_role("button", name="Send", exact=True).click()


def wait_for_stream_response(
    page: Page, stream_responses: list[APIResponse]
) -> APIResponse:
    deadline = time.monotonic() + STREAM_TIMEOUT_SECONDS
    while not stream_responses:
        if time.monotonic() >= deadline:
            pytest.fail(
                f"{STREAM_PATH} did not finish within "
                f"{STREAM_TIMEOUT_SECONDS} seconds"
            )
        page.wait_for_timeout(POLL_INTERVAL_MS)
    return stream_responses[0]


def check_content_delta_streamed(stream_response: APIResponse) -> None:
    body = stream_response.text()
    assert stream_response.status == 200, (
        f"{STREAM_PATH} returned {stream_response.status}: {body}"
    )
    events = parse_stream_events(body)
    error_messages = [
        event["message"] for event in events if event["type"] == "error"
    ]
    assert not error_messages, (
        f"{STREAM_PATH} streamed an error event: {error_messages}"
    )
    event_types = [event["type"] for event in events]
    assert "content_delta" in event_types, (
        f"{STREAM_PATH} streamed no content_delta event. "
        f"Event types: {event_types}"
    )


def parse_stream_events(body: str) -> list[dict]:
    # Same framing as chatApp.sendMessage: each "data: " line is one event.
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
