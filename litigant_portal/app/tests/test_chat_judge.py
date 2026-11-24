import json
from types import SimpleNamespace
from unittest.mock import DEFAULT, patch

import pytest
from django.core.cache import cache
from litellm import Timeout

from litigant_portal.agents.assistant import LitigantAssistant
from litigant_portal.agents.base import (
    Agent,
    IdentityPrompt,
    ToolOutput,
    TurnTimeContext,
)
from litigant_portal.agents.bedrock import ResolvedBedrockModel
from litigant_portal.app.models import ChatThread, Site, UserIdentity, Variable
from litigant_portal.app.selectors.chat_engine import (
    chat_message_list,
    chat_thread_export_data,
    chat_thread_export_markdown,
    chat_thread_usage,
)
from litigant_portal.app.services.chat_engine import (
    chat_message_create,
    chat_stream,
    chat_thread_render_items,
)
from litigant_portal.app.services.corpus import corpus_sync
from litigant_portal.app.services.topic_flow import variable_answer_set

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]
MODEL = "bedrock_mantle/openai.gpt-5.6-luna"
JUDGE = "bedrock_mantle/openai.gpt-5.6-sol"
FINDING = {"code": "unsupported_claim", "message": "Remove the invented fee."}
WARNING = (
    "Warning: This answer could not be fully verified and may contain errors."
)


class JudgeTestAgent(Agent):
    def generate_system_prompt(self, *, thread_id) -> str:
        return "Supplied court information."

    def generate_identity_prompt(
        self, *, thread_id, time_context: TurnTimeContext | None = None
    ) -> IdentityPrompt:
        return IdentityPrompt(
            text="Saved name: Alex",
            values={"name": "Alex"},
            render_snapshot=lambda: {
                "text": "Saved name: [private]",
                "values": {},
            },
        )


def generation(text, tool_calls=None):
    return iter(
        [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=part, tool_calls=tool_calls or []
                        )
                    )
                ],
                usage=SimpleNamespace(completion_tokens=10),
            )
            for part in (text[:3], text[3:])
        ]
    )


def review(approved):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "approved": approved,
                            "findings": [] if approved else [FINDING],
                        }
                    ),
                    tool_calls=None,
                ),
            )
        ],
        usage=SimpleNamespace(completion_tokens=5),
    )


@pytest.fixture
def stream():
    identity = UserIdentity.objects.create(session_key="judge-test")
    thread = ChatThread.objects.create(identity=identity, description="Test")

    def run(responses, judge_model=JUDGE, *, agent_class=JudgeTestAgent):
        Site.objects.update(judge_model=judge_model)
        cache.clear()
        with (
            patch(
                "litigant_portal.app.services.chat_engine.bedrock_model_target",
                side_effect=lambda *, model, **kwargs: ResolvedBedrockModel(
                    model, "us-east-1", small_task_effort="low"
                ),
            ),
            patch(
                "litigant_portal.app.services.chat_engine.litellm.completion",
                side_effect=responses,
            ) as completion,
            patch(
                "litigant_portal.app.services.chat_engine.litellm.completion_cost",
                return_value=0.1,
            ),
            patch(
                "litigant_portal.app.services.chat_engine.litellm.token_counter",
                return_value=1,
            ),
        ):
            response = chat_stream(
                identity=identity,
                message="What do I file?",
                agent_class=agent_class,
                thread_type="user_chat",
                model=MODEL,
                thread_id=str(thread.id),
            )
            events = []
            for frame in response.streaming_content:
                event = json.loads(frame.decode().removeprefix("data: "))
                if judge_model and event["type"] == "content_delta":
                    saved = thread.messages.get(
                        meta=False, data__content=event["content"]
                    )
                    assert saved.data.get("review_warning") == event.get(
                        "review_warning"
                    ), "Display must follow persistence"
                    items = chat_thread_render_items(
                        thread=thread, agent_class=agent_class
                    )
                    assert items[-1].get("review_warning") == event.get(
                        "review_warning"
                    )
                events.append(event)
            return events, completion.call_args_list

    return thread, run


@pytest.mark.parametrize("judge_model", [None, JUDGE])
def test_fact_becomes_private_during_stream(stream, judge_model):
    thread, run = stream
    changing = Variable.objects.create(name="changing_fact")
    public = Variable.objects.create(name="public_fact")
    variable_answer_set(
        identity=thread.identity, variable=changing, value="privacy-sentinel"
    )
    variable_answer_set(
        identity=thread.identity, variable=public, value="public-sentinel"
    )

    def response():
        chunks = generation("Draft reply.")
        yield next(chunks)
        assert not thread.messages.filter(data__role="assistant").exists()
        Variable.objects.filter(pk=changing.pk).update(is_private=True)
        yield from chunks

    responses = [response()]
    if judge_model:
        responses.extend(
            [review(False), generation("Final reply."), review(True)]
        )
    _, calls = run(responses, judge_model, agent_class=LitigantAssistant)
    model_calls = calls[::2] if judge_model else calls
    public_value = 'value: "public-sentinel", display_value: "public-sentinel"'
    public_line = f"- public_fact (public_fact): {public_value} [unconfirmed]"
    private_line = "- changing_fact (changing_fact): [private] [unconfirmed]"
    for call in model_calls:
        prompt = call.kwargs["messages"][0]["content"]
        assert (
            '- changing_fact (changing_fact): value: "privacy-sentinel", '
            'display_value: "privacy-sentinel" [unconfirmed]' in prompt
        )
        assert public_line in prompt

    messages = thread.messages.filter(data__role="assistant").order_by(
        "created_at"
    )
    assert [message.meta for message in messages] == (
        [True, False] if judge_model else [False]
    )
    for message in messages:
        assert private_line in message.identity_prompt["text"]
        assert public_line in message.identity_prompt["text"]
        assert message.identity_prompt["values"] == {
            "public_fact": public_value
        }

    markdown = chat_thread_export_markdown(thread=thread)
    assert private_line in markdown
    assert public_line in markdown
    assert "privacy-sentinel" not in markdown
    assert "privacy-sentinel" not in json.dumps(
        chat_thread_export_data(thread=thread)
    )


def test_fact_retired_during_stream_is_masked_in_message(stream, tmp_path):
    thread, run = stream
    glossary = tmp_path / "variables.yml"
    active_variables = (
        "variables:\n"
        "  - name: public_fact\n"
        "    label: Public fact\n"
        "  - name: private_fact\n"
        "    label: Private fact\n"
        "    private: true\n"
    )
    glossary.write_text(
        active_variables + "  - name: retired_fact\n    label: Retired fact\n",
        encoding="utf-8",
    )
    corpus_sync(root=tmp_path)
    for name, value in (
        ("retired_fact", "retired-answer"),
        ("private_fact", "private-answer"),
        ("public_fact", "public-answer"),
    ):
        variable_answer_set(
            identity=thread.identity,
            variable=Variable.objects.get(name=name),
            value=value,
        )

    def response():
        chunks = generation("Reply.")
        yield next(chunks)
        glossary.write_text(active_variables, encoding="utf-8")
        corpus_sync(root=tmp_path)
        yield from chunks

    _, calls = run([response()], None, agent_class=LitigantAssistant)
    retired = Variable.objects.get(name="retired_fact")
    assert not retired.in_schema
    assert not retired.is_private
    model_text = calls[0].kwargs["messages"][0]["content"]
    assert (
        '- retired_fact (Retired fact): value: "retired-answer", '
        'display_value: "retired-answer" [unconfirmed]' in model_text
    )
    assert (
        '- private_fact (Private fact): value: "private-answer", '
        'display_value: "private-answer" [unconfirmed]' in model_text
    )

    stored = thread.messages.get(data__role="assistant").identity_prompt
    public_value = 'value: "public-answer", display_value: "public-answer"'
    public_line = f"- public_fact (Public fact): {public_value} [unconfirmed]"
    retired_line = "- retired_fact (Retired fact): [private] [unconfirmed]"
    private_line = "- private_fact (Private fact): [private] [unconfirmed]"
    assert public_line in model_text
    assert stored["values"] == {"public_fact": public_value}
    for line in (retired_line, private_line, public_line):
        assert line in stored["text"]

    markdown = chat_thread_export_markdown(thread=thread)
    assert retired_line in markdown
    assert "retired-answer" not in markdown
    assert "retired-answer" not in json.dumps(
        chat_thread_export_data(thread=thread)
    )


@pytest.mark.parametrize("judge_model", [None, ""])
def test_disabled_preserves_streaming(stream, judge_model):
    thread, run = stream
    events, calls = run([generation("Original")], judge_model)
    assert [e["content"] for e in events if e["type"] == "content_delta"] == [
        "Ori",
        "ginal",
    ]
    assert len(calls) == 1
    assert "timeout" not in calls[0].kwargs
    assert "num_retries" not in calls[0].kwargs
    assert "max_tokens" not in calls[0].kwargs
    assert not any(event["type"] == "heartbeat" for event in events)
    assert not thread.messages.filter(meta=True).exists()
    assert not any("review_warning" in event for event in events)


@pytest.mark.parametrize("rejections", [0, 1, 2, 3])
def test_review_loop_audit_and_cost(stream, rejections, caplog):
    thread, run = stream
    attempts = min(rejections + 1, 3)
    responses = []
    for attempt in range(attempts):
        responses.extend(
            [generation(f"Draft {attempt}"), review(attempt >= rejections)]
        )
    events, calls = run(responses)
    assert [e["content"] for e in events if e["type"] == "content_delta"] == [
        f"Draft {attempts - 1}"
    ]
    assert sum(e["type"] == "judging" for e in events) == attempts
    assert sum(e["type"] == "heartbeat" for e in events) == attempts
    for call in (call for call in calls if not call.kwargs["stream"]):
        assert call.kwargs["max_tokens"] == 4096
        assert call.kwargs["reasoning_effort"] == "low"
    for call in calls:
        assert call.kwargs["timeout"] == 45
        assert call.kwargs["num_retries"] == 0
    assert events[-1] == {"type": "done"}
    export = chat_thread_export_data(thread=thread)
    audits = [
        m["data"]
        for m in export["messages"]
        if m["data"].get("kind") == "judge"
    ]
    assert len(audits) == attempts
    assert audits[0]["verdict"]["approved"] is (rejections == 0)
    rejected = thread.messages.filter(meta=True, data__role="assistant")
    assert rejected.count() == min(rejections, 3)
    assert not rejected.filter(hidden=True).exists()
    assert not rejected.filter(data__has_key="review_warning").exists()
    expected_snapshot = {"text": "Saved name: [private]", "values": {}}
    snapshots = [
        message["identity_prompt"]
        for message in export["messages"]
        if message["data"]["role"] == "assistant"
    ]
    assert snapshots == [expected_snapshot] * (min(rejections, 3) + 1)
    expected_warning = True if rejections == 3 else None
    released = next(e for e in events if e["type"] == "content_delta")
    assert released.get("review_warning") == expected_warning
    visible = [m["data"] for m in export["messages"] if not m["meta"]]
    assert visible[-1].get("review_warning") == expected_warning
    markdown = chat_thread_export_markdown(thread=thread)
    assert ("[unverified]" in markdown) is (rejections == 3)
    assert "Saved name: [private]" in markdown
    assert "Saved name: Alex" not in markdown
    assert chat_thread_usage(thread=thread)["total_cost"] == pytest.approx(
        attempts * 0.2
    )
    assert (
        chat_thread_usage(thread=thread)["total_tokens"] == 1 + attempts * 15
    )
    replay = [
        m.data for m in chat_message_list(thread=thread, exclude_meta=True)
    ]
    assert len(replay) == 2
    for generation_call, judge_call in zip(
        calls[::2], calls[1::2], strict=True
    ):
        model_prompt = generation_call.kwargs["messages"][0]["content"]
        judge_request = json.loads(judge_call.kwargs["messages"][1]["content"])
        assert (
            model_prompt == "Supplied court information.\n\nSaved name: Alex"
        )
        assert judge_request["messages"][0]["content"] == model_prompt
    if rejections:
        assert audits[0]["verdict"]["findings"][0] == FINDING
        assert "invented fee" in json.dumps(calls[2].kwargs["messages"])
        correction = calls[2].kwargs["messages"][-1]
        assert correction["content"].startswith(
            "Internal review feedback, not a new user request."
        )
        next_review = json.loads(calls[3].kwargs["messages"][1]["content"])
        assert next_review["messages"][-1] == correction
    if rejections == 3:
        assert "corrections exhausted" in caplog.text
        legacy = thread.messages.filter(
            meta=False, data__role="assistant"
        ).last()
        legacy.data["review_warning"] = WARNING
        legacy.save()
        assert (
            chat_thread_render_items(
                thread=thread, agent_class=JudgeTestAgent
            )[-1]["review_warning"]
            is True
        )
        assert (
            chat_thread_export_data(thread=thread)["messages"][-1]["data"][
                "review_warning"
            ]
            == WARNING
        )
        markdown = chat_thread_export_markdown(thread=thread)
        assert "[unverified]" in markdown
        assert WARNING not in markdown
        _, followup_calls = run([generation("Follow-up"), review(True)])
        previous_answer = next(
            message
            for message in followup_calls[0].kwargs["messages"]
            if message["role"] == "assistant"
        )
        assert previous_answer == {"role": "assistant", "content": "Draft 2"}


@pytest.mark.parametrize(
    "category", ["timeout", "provider_error", "invalid_output"]
)
def test_judge_failure_releases_and_books_returned_usage(
    stream, category, caplog
):
    thread, run = stream
    reply = review(True)
    reply.choices[0].message.content = "private-judge-detail"
    failures = {
        "invalid_output": reply,
        "provider_error": RuntimeError("private-judge-detail"),
        "timeout": Timeout(
            message="private-judge-detail", model=JUDGE, llm_provider="bedrock"
        ),
    }
    events, _ = run([generation("Answer"), failures[category]])
    assert {
        "type": "content_delta",
        "content": "Answer",
        "review_warning": True,
    } in events
    assert "judge failed" in caplog.text
    assert "private-judge-detail" not in caplog.text
    assert chat_thread_usage(thread=thread)["total_cost"] == pytest.approx(
        0.2 if category == "invalid_output" else 0.1
    )
    audit = next(
        message["data"]
        for message in chat_thread_export_data(thread=thread)["messages"]
        if message["data"].get("kind") == "judge"
    )
    assert audit["error"] == "judge_failed"
    assert audit["error_category"] == category
    if category == "invalid_output":
        assert audit["content"] == "private-judge-detail"


def test_buffered_generation_emits_throttled_progress(stream):
    thread, run = stream
    clock = SimpleNamespace(now=0)

    def slow_generation():
        for seconds in (1, 9, 10, 11, 20, 29, 30, 40, 50, 60, 70):
            clock.now = seconds
            if seconds in (10, 20):
                yield SimpleNamespace(choices=[], usage=None)
            else:
                yield next(generation("Answer"))

    with patch(
        "litigant_portal.app.services.chat_engine.monotonic",
        side_effect=lambda: clock.now,
        create=True,
    ):
        events, _ = run([slow_generation(), review(True)])
    assert [event["type"] for event in events] == [
        "thread",
        "state",
        *["heartbeat"] * 8,
        "judging",
        "content_delta",
        "done",
    ]
    assert not thread.messages.filter(data__type="heartbeat").exists()


@pytest.mark.parametrize("correction", [False, True])
def test_generation_timeout_uses_fallback_without_releasing_draft(
    stream, correction
):
    thread, run = stream
    responses = [generation("Rejected"), review(False)] if correction else []
    responses.append(
        Timeout(message="Timed out", model=MODEL, llm_provider="bedrock")
    )
    events, _ = run(responses)
    assert events[-2]["type"] == "error"
    assert events[-2]["fallback_url"] == "/"
    assert events[-1]["type"] == "done"
    assert not any(event["type"] == "content_delta" for event in events)
    assert not thread.messages.filter(
        meta=False, data__role="assistant"
    ).exists()
    assert events[-3]["type"] == "heartbeat"


def test_tool_prose_releases_without_review(stream):
    _, run = stream
    tool = SimpleNamespace(
        index=0,
        id="load",
        function=SimpleNamespace(name="LoadTopicFlow", arguments="{}"),
    )
    chunks = list(generation("Loading"))
    chunks[-1].choices[0].delta.tool_calls = [tool]
    with patch(
        "litigant_portal.app.services.chat_engine._execute_tool",
        return_value=ToolOutput(result="Source text"),
    ):
        events, calls = run([iter(chunks), generation("Answer"), review(True)])
    assert [e["content"] for e in events if e["type"] == "content_delta"] == [
        "Loading",
        "Answer",
    ]
    assert [c.kwargs["model"] for c in calls] == [MODEL, MODEL, JUDGE]
    assert "Source text" in calls[-1].kwargs["messages"][1]["content"]


@pytest.mark.parametrize(
    ("successful_writes", "rejections"), [(1, 0), (2, 0), (2, 1), (7, 3)]
)
def test_failed_write_never_releases_candidate(
    stream, successful_writes, rejections
):
    _, run = stream
    responses = []
    for _ in range(max(rejections, 1)):
        responses.extend([generation("Answer"), review(not rejections)])
    with patch(
        "litigant_portal.app.services.chat_engine.chat_message_create",
        wraps=chat_message_create,
        side_effect=[DEFAULT] * successful_writes
        + [RuntimeError("database unavailable")],
    ):
        events, _ = run(responses)
    assert not any(e["type"] == "content_delta" for e in events)
    assert events[-2]["type"] == "error"
