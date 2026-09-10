"""
Responses normalization and SDK stream ownership, without live provider calls.
"""

import asyncio
import json
from contextlib import aclosing
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue
from threading import Thread
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from litellm import CustomStreamWrapper
from litellm.litellm_core_utils.litellm_logging import Logging
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
from litellm.types.llms.openai import ResponsesAPIResponse
from litellm.types.utils import ModelResponseStream

from lp_agent import AgentValidationError, LPAgent, RunLimits
from lp_agent.adapters.bedrock import MODEL_CHOICES, BedrockClient
from lp_agent.adapters.environment import create_environment
from lp_agent.tests.helpers import environment_options
from lp_agent.types import (
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    ReasoningItem,
    ToolDefinition,
)

GLM_MODEL = "bedrock_mantle/zai.glm-4.7-flash"


@pytest.fixture
def http_clients(monkeypatch):
    clients = []
    create = AsyncHTTPHandler.create_client

    def create_client(handler, **kwargs):
        client = create(handler, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(AsyncHTTPHandler, "create_client", create_client)
    return clients


def message(text="Hello", **metadata):
    return {
        "type": "message",
        "role": "assistant",
        "id": "msg_1",
        "status": "completed",
        "content": [
            {
                "type": "output_text",
                "text": text,
                "annotations": [],
            }
        ],
        **metadata,
    }


def reasoning():
    return {
        "type": "reasoning",
        "id": "rs_1",
        "status": "completed",
        "summary": [{"type": "summary_text", "text": "Private summary"}],
        "encrypted_content": "opaque-continuation",
    }


def text_event(text):
    return {
        "type": "response.output_text.delta",
        "delta": text,
        "output_index": 0,
        "item_id": "msg_1",
        "content_index": 0,
        "sequence_number": 1,
        "logprobs": [],
    }


def done(item, index=0):
    return {
        "type": "response.output_item.done",
        "output_index": index,
        "item": item,
        "sequence_number": index + 2,
    }


def terminal(
    output, *, status="completed", kind="response.completed", reason=None
):
    response = ResponsesAPIResponse(
        id="resp_1",
        created_at=0,
        model=MODEL_CHOICES[0][0],
        status=status,
        output=output,
        incomplete_details={"reason": reason} if reason else None,
    )
    return {
        "type": kind,
        "response": response.model_dump(mode="json"),
        "sequence_number": 10,
    }


async def events(*values):
    for value in values:
        if isinstance(value, Exception):
            raise value
        yield value


def collect(*values):
    async def scenario():
        with patch(
            "litellm.aresponses", AsyncMock(return_value=events(*values))
        ):
            return [
                event
                async for event in BedrockClient(
                    MODEL_CHOICES[0][0], api_key="test-only-key"
                ).stream(ModelRequest(input=()))
            ]

    return asyncio.run(scenario())


def test_stream_preserves_complete_items_and_metadata_once_in_provider_order():
    output = message(phase="final_answer")
    output["content"][0].update(
        annotations=[
            {
                "type": "url_citation",
                "url": "https://example.org",
                "title": "Source",
            }
        ],
        logprobs=[{"token": "Hello", "logprob": -0.1}],
    )
    result = collect(
        {
            "type": "response.reasoning_summary_text.delta",
            "delta": "Private summary",
        },
        done(reasoning()),
        text_event("Hel"),
        text_event("lo"),
        done(output, 1),
        terminal([reasoning(), output]),
    )
    assert [event.type for event in result] == [
        "text",
        "text",
        "output_item",
        "output_item",
        "finished",
    ]
    assert result[2].item.model_dump(mode="json") == reasoning()
    assert result[3].item.model_dump(mode="json") == output
    assert result[-1].reason == "stop"


def test_terminal_output_order_and_metadata_override_buffered_items():
    result = collect(
        done(message(status="in_progress")),
        done(reasoning(), 1),
        terminal([reasoning(), message(phase="final_answer")]),
    )
    assert [event.item.id for event in result[:-1]] == ["rs_1", "msg_1"]
    assert result[1].item.status == "completed"
    assert result[1].item.phase == "final_answer"
    assert result[-1].reason == "stop"


def test_native_request_preserves_instructions_and_continuation_and_closes():
    async def scenario():
        closed = False

        async def provider():
            nonlocal closed
            try:
                yield terminal([message()])
            finally:
                closed = True

        request = ModelRequest(
            instructions="  Scoped instructions\n",
            input=(
                ReasoningItem(**reasoning()),
                ModelMessage(**message(phase="final_answer")),
                ModelMessage(role="user", content=" Next turn "),
            ),
        )
        call = AsyncMock(return_value=provider())
        with patch("litellm.aresponses", call):
            result = [
                event
                async for event in BedrockClient(
                    MODEL_CHOICES[0][0], api_key="explicit-key"
                ).stream(request)
            ]
        assert result[-1].reason == "stop"
        assert closed
        args = call.call_args.kwargs
        assert args["model"] == MODEL_CHOICES[0][0]
        assert args["instructions"] == request.instructions
        assert args["input"] == request.model_dump(mode="json")["input"]
        assert args["api_key"] == "explicit-key"
        assert args["include"] == ["reasoning.encrypted_content"]
        assert args["stream"] and args["num_retries"] == 0
        assert args["store"] is False and args["caching"] is False
        assert "tools" not in args

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status,detail,expected",
    [
        ("incomplete", "max_output_tokens", "length"),
        ("incomplete", "content_filter", "content_filter"),
        ("incomplete", None, "other"),
        ("in_progress", None, "other"),
    ],
)
def test_completed_event_name_does_not_override_response_status(
    status, detail, expected
):
    result = collect(
        terminal([message(status="incomplete")], status=status, reason=detail)
    )
    assert result[-1].reason == expected


def test_eof_keeps_completed_items_without_claiming_success():
    result = collect(text_event("Partial"), done(reasoning()))
    assert [event.type for event in result] == ["text", "output_item"]


def test_failed_response_and_error_event_raise_without_provider_details():
    for event in (
        terminal([], status="failed", kind="response.failed"),
        {"type": "error", "message": "private provider details"},
    ):
        with pytest.raises(
            RuntimeError, match="model response failed"
        ) as error:
            collect(event)
        assert "private" not in str(error.value)


def test_actual_function_call_is_preserved_as_an_item():
    call = {
        "type": "function_call",
        "id": "fc_1",
        "call_id": "call_1",
        "name": "lookup",
        "arguments": '{ "query": "court" }',
        "status": "completed",
    }
    result = collect(done(call), terminal([call]))
    assert result[0].item.model_dump(mode="json") == call
    assert result[-1].reason == "tool_calls"


@pytest.mark.parametrize(
    "item",
    [
        ReasoningItem(**reasoning()),
        ModelMessage(**message(phase="commentary")),
    ],
)
def test_translated_model_rejects_unrepresentable_continuation_before_call(
    item,
):
    async def scenario():
        with patch("litellm.aresponses") as call:
            with pytest.raises(
                AgentValidationError, match="continuation metadata"
            ):
                _ = [
                    event
                    async for event in BedrockClient(
                        GLM_MODEL, api_key="test-key"
                    ).stream(ModelRequest(input=(item,)))
                ]
            call.assert_not_called()

    asyncio.run(scenario())


def test_tools_remain_explicitly_unavailable_before_call():
    async def scenario():
        request = ModelRequest(
            input=(),
            tools=(
                ToolDefinition(
                    name="lookup",
                    description="Lookup",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                ),
            ),
        )
        with patch("litellm.aresponses") as call:
            with pytest.raises(NotImplementedError, match="Tool calls"):
                _ = [
                    event
                    async for event in BedrockClient(
                        MODEL_CHOICES[0][0], api_key="test-key"
                    ).stream(request)
                ]
            call.assert_not_called()

    asyncio.run(scenario())


class NativeBody(httpx.AsyncByteStream):
    """
    Real HTTP streaming semantics with controlled Responses events.
    """

    def __init__(self, values, *, stall=False):
        self.values = values
        self.stall = stall
        self.stalled = asyncio.Event()
        self.closed = False

    async def __aiter__(self):
        for value in self.values:
            if isinstance(value, Exception):
                raise value
            yield ("data: " + json.dumps(value) + "\n\n").encode()
        if self.stall:
            self.stalled.set()
            await asyncio.Event().wait()

    async def aclose(self):
        self.closed = True


def native_response(values, *, stall=False):
    body = NativeBody(values, stall=stall)
    response = httpx.Response(
        200,
        stream=body,
        request=httpx.Request("POST", "https://provider.invalid"),
        headers={"content-type": "text/event-stream"},
    )
    return body, response


def translated_stream(stream):
    logging = Logging(
        model="gpt-4o-mini",
        messages=[],
        stream=True,
        call_type="acompletion",
        start_time=datetime.now(),
        litellm_call_id="test-call",
        function_id="test-function",
    )
    return CustomStreamWrapper(
        completion_stream=stream,
        model="gpt-4o-mini",
        custom_llm_provider="openai",
        logging_obj=logging,
    )


@pytest.mark.parametrize("request_fails", [False, True])
def test_http_client_closes_after_request_or_response_cleanup_failure(
    request_fails, http_clients
):
    async def provider():
        try:
            yield terminal([message()])
        finally:
            raise RuntimeError("Response cleanup failed")

    async def scenario():
        call = (
            AsyncMock(side_effect=RuntimeError("Request failed"))
            if request_fails
            else AsyncMock(return_value=provider())
        )
        with patch("litellm.aresponses", call), pytest.raises(RuntimeError):
            _ = [
                event
                async for event in BedrockClient(
                    MODEL_CHOICES[0][0], api_key="test-key"
                ).stream(ModelRequest(input=()))
            ]
        assert http_clients and all(
            client.is_closed for client in http_clients
        )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadError("private provider payload"),
        {"type": "error", "message": "private provider payload"},
        terminal([], status="failed", kind="response.failed"),
    ],
)
def test_stream_failure_retains_completed_items_in_checkpoint(
    failure, http_clients, caplog
):
    body, response = native_response(
        [done(reasoning()), text_event("Hello"), done(message(), 1), failure]
    )
    environment = create_environment(**environment_options())
    with patch.object(
        AsyncHTTPHandler, "post", AsyncMock(return_value=response)
    ):
        output = [
            json.loads(line)
            for line in LPAgent(environment=environment).stream(
                message="Hello"
            )
        ]
    checkpoint = asyncio.run(
        environment.runs.checkpoint(
            access=environment.access, run_id=output[0]["run_id"]
        )
    )
    assert checkpoint.data["model_output"] == [reasoning(), message()]
    assert checkpoint.data["model_finished"] is None
    assert output[-1]["payload"]["outcome"]["state"] == "failed"
    assert "private provider payload" not in json.dumps(output) + caplog.text
    assert "Private summary" not in json.dumps(output)
    assert body.closed and response.is_closed
    assert http_clients and all(client.is_closed for client in http_clients)


@pytest.mark.parametrize("termination", ["timeout", "cancel", "shutdown"])
@pytest.mark.parametrize("completed_items", [False, True])
def test_interrupted_response_preserves_completed_items_in_checkpoint(
    termination, completed_items, http_clients, caplog
):
    async def scenario():
        expected = [reasoning(), message()] if completed_items else []
        body, response = native_response(
            [done(item, index) for index, item in enumerate(expected)],
            stall=True,
        )
        environment = create_environment(**environment_options())
        with patch.object(
            AsyncHTTPHandler, "post", AsyncMock(return_value=response)
        ):
            async with LPAgent(
                environment=environment,
                limits=RunLimits(
                    max_active_seconds=1.0 if termination == "timeout" else 5
                ),
            ) as agent:
                run = await agent.run(message="Hello")
                await asyncio.wait_for(body.stalled.wait(), timeout=2)
                if termination == "cancel":
                    await asyncio.wait_for(run.cancel(), timeout=2)
                elif termination == "shutdown":
                    await asyncio.wait_for(agent.aclose(), timeout=2)
                outcome = await asyncio.wait_for(run.result(), timeout=2)
                if termination == "timeout":
                    assert outcome.state == "failed"
                    assert outcome.error.code == "active_time_limit"
                else:
                    assert outcome.state == "cancelled"
                assert (await run.status()).state == outcome.state
                public_events = "".join(
                    [event.model_dump_json() async for event in run.events()]
                )
        checkpoint = await environment.runs.checkpoint(
            access=environment.access, run_id=run.run_id
        )
        assert checkpoint.data["model_output"] == expected
        assert checkpoint.data["model_finished"] is None
        assert body.closed and response.is_closed
        assert http_clients and all(
            client.is_closed for client in http_clients
        )
        for private in (
            "Private summary",
            "opaque-continuation",
            "test-only-key",
        ):
            assert private not in public_events + caplog.text

    asyncio.run(scenario())


@pytest.mark.parametrize("model", [MODEL_CHOICES[0][0], GLM_MODEL])
def test_repeated_sync_requests_close_clients_and_connections(
    model, http_clients
):
    disconnected = Queue()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            values = [text_event("Hello"), terminal([message()])]
            if model == GLM_MODEL:
                values = [
                    {
                        "id": "chatcmpl-1",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": "zai.glm-4.7-flash",
                        "choices": [
                            {
                                "index": 0,
                                "delta": delta,
                                "finish_reason": finish,
                            }
                        ],
                    }
                    for delta, finish in [
                        ({"content": "Hello"}, None),
                        ({}, "stop"),
                    ]
                ]
            body = "".join(
                "data: " + json.dumps(value) + "\n\n" for value in values
            )
            body = (body + "data: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def finish(self):
            try:
                super().finish()
            finally:
                disconnected.put(None)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    post = AsyncHTTPHandler.post
    loops = []

    async def local_post(handler, url, **kwargs):
        loops.append(asyncio.get_running_loop())
        return await post(
            handler, f"http://127.0.0.1:{server.server_port}", **kwargs
        )

    try:
        with patch.object(AsyncHTTPHandler, "post", local_post):
            for _ in range(3):
                environment = create_environment(
                    **(environment_options() | {"model": model})
                )
                output = [
                    json.loads(line)
                    for line in LPAgent(environment=environment).stream(
                        message="Hello"
                    )
                ]
                assert output[-1]["payload"]["outcome"]["state"] == "completed"
                assert http_clients and all(
                    client.is_closed for client in http_clients
                )
                assert loops[-1].is_closed()
                disconnected.get(timeout=2)
        assert len(loops) == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("early", [False, True])
@pytest.mark.parametrize("choice", [0, 1, 2])
def test_real_native_litellm_stream_releases_http_response(
    early, choice, http_clients
):
    async def scenario():
        body, http_response = native_response(
            [
                done(reasoning()),
                text_event("Hello") | {"output_index": 1},
                terminal([reasoning(), message()]),
            ],
            stall=early,
        )
        with patch.object(
            AsyncHTTPHandler, "post", AsyncMock(return_value=http_response)
        ) as post:
            stream = BedrockClient(
                MODEL_CHOICES[choice][0], api_key="test-key"
            ).stream(
                ModelRequest(
                    instructions="Scope",
                    input=(ModelMessage(role="user", content="Hello"),),
                )
            )
            async with aclosing(stream):
                assert (await anext(stream)).delta == "Hello"
                if not early:
                    remaining = [event async for event in stream]
                    assert remaining[-1].reason == "stop"
            with pytest.raises(StopAsyncIteration):
                await anext(stream)
        assert body.closed and http_response.is_closed
        assert http_clients and all(
            client.is_closed for client in http_clients
        )
        assert "/responses" in str(post.call_args)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "finish", ["stop", "length", "content_filter", None, "unknown"]
)
def test_real_translated_litellm_stream_preserves_reasoning_and_finish(
    finish, http_clients
):
    async def scenario():
        closed = False

        async def provider():
            nonlocal closed
            try:
                yield ModelResponseStream(
                    choices=[
                        {"delta": {"reasoning_content": "Private thinking"}}
                    ]
                )
                yield ModelResponseStream(
                    choices=[{"delta": {"content": "Hello"}}]
                )
                if finish is not None:
                    chunk = ModelResponseStream(
                        choices=[{"delta": {}, "finish_reason": finish}]
                    )
                    # SDK construction normalizes unknown strings to stop. Model
                    # an upstream unknown value before CustomStreamWrapper sees it.
                    chunk.choices[0].finish_reason = finish
                    yield chunk
            finally:
                closed = True

        wrapper = translated_stream(provider())
        with patch(
            "litellm.acompletion", AsyncMock(return_value=wrapper)
        ) as call:
            result = [
                event
                async for event in BedrockClient(
                    GLM_MODEL, api_key="test-key"
                ).stream(
                    ModelRequest(
                        instructions="Scope",
                        input=(ModelMessage(role="user", content="Hello"),),
                    )
                )
            ]
        assert closed
        assert http_clients and all(
            client.is_closed for client in http_clients
        )
        assert result[-1].reason == (
            finish
            if finish in {"stop", "length", "content_filter"}
            else "other"
        )
        output = [
            event.item
            for event in result
            if isinstance(event, ModelOutputItem)
        ]
        assert [item.type for item in output] == ["reasoning", "message"]
        assert output[0].content[0].text == "Private thinking"
        assert output[1].content[0].text == "Hello"
        assert all(
            event.delta != "Private thinking"
            for event in result
            if event.type == "text"
        )
        assert call.call_args.kwargs["api_key"] == "test-key"

    asyncio.run(scenario())


@pytest.mark.parametrize("translated", [False, True])
@pytest.mark.parametrize("timeout", [False, True])
def test_agent_cancellation_and_timeout_close_actual_litellm_wrappers(
    translated, timeout, http_clients
):
    async def scenario():
        closed = False

        async def provider():
            nonlocal closed
            try:
                yield ModelResponseStream(
                    choices=[{"delta": {"content": "Hello"}}]
                )
                await asyncio.Event().wait()
            finally:
                closed = True

        if translated:
            wrapper = translated_stream(provider())
            provider_patch = patch(
                "litellm.acompletion", AsyncMock(return_value=wrapper)
            )
        else:
            body, http_response = native_response(
                [text_event("Hello")], stall=True
            )
            provider_patch = patch.object(
                AsyncHTTPHandler, "post", AsyncMock(return_value=http_response)
            )
        environment = create_environment(
            **(
                environment_options()
                | {"model": GLM_MODEL if translated else MODEL_CHOICES[0][0]}
            )
        )
        with provider_patch:
            async with LPAgent(
                environment=environment,
                limits=RunLimits(max_active_seconds=0.2 if timeout else 5),
            ) as agent:
                run = await agent.run(message="Hello")
                async with aclosing(run.events()) as observer:
                    await anext(observer)
                    assert (
                        await asyncio.wait_for(anext(observer), timeout=2)
                    ).payload.delta == "Hello"
                    if timeout:
                        outcome = await asyncio.wait_for(
                            run.result(), timeout=2
                        )
                        assert outcome.state == "failed"
                        assert outcome.error.code == "active_time_limit"
                    await asyncio.wait_for(agent.aclose(), timeout=2)
                    if not timeout:
                        assert (await run.result()).state == "cancelled"
        assert (
            closed if translated else body.closed and http_response.is_closed
        )
        assert http_clients and all(
            client.is_closed for client in http_clients
        )
        checkpoint = await environment.runs.checkpoint(
            access=environment.access, run_id=run.run_id
        )
        assert checkpoint.data["model_finished"] is None
        assert checkpoint.data["instruction_artifact"]["sha256"]

    asyncio.run(scenario())


def test_supplied_key_reaches_provider_but_not_run_data_or_events(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "unused-environment-key")
    environment = create_environment(**environment_options())
    call = AsyncMock(
        return_value=events(
            text_event("Hello"), terminal([reasoning(), message()])
        )
    )
    with patch("litellm.aresponses", call):
        output = [
            json.loads(line)
            for line in LPAgent(environment=environment).stream(
                message="Hello"
            )
        ]
    checkpoint = asyncio.run(
        environment.runs.checkpoint(
            access=environment.access, run_id=output[0]["run_id"]
        )
    )
    serialized = json.dumps(output) + checkpoint.model_dump_json()
    assert output[-1]["payload"]["outcome"]["state"] == "completed"
    assert call.call_args.kwargs["api_key"] == "test-only-key"
    assert "test-only-key" not in serialized and "api_key" not in serialized
    assert "Private summary" not in json.dumps(output)
    assert "opaque-continuation" in checkpoint.model_dump_json()
