import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest

from lp_agent import AgentAccessError, AgentValidationError
from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.adapters.environment import create_environment
from lp_agent.tests.helpers import environment_options
from lp_agent.types import AccessContext, Scope, ScopeSelection


def test_callbacks_resolve_once_at_initialization_and_are_not_retained(
    tmp_path,
):
    options = environment_options() | {
        "resource_root": tmp_path / "missing-corpus",
        "judge": MODEL_CHOICES[1][0],
    }
    callbacks = {
        name: Mock(return_value=value)
        for name, value in options.items()
        if name not in {"court", "topic"}
    }
    environment = create_environment(**(options | callbacks))
    for callback in callbacks.values():
        callback.assert_called_once_with()
        callback.side_effect = AssertionError("Must not resolve again")

    async def scenario():
        for _ in range(2):
            scoped = await environment.scope_factory.bind(
                access=environment.access,
                scope=Scope(court="court", topic="topic"),
            )
            assert scoped.model.model == MODEL_CHOICES[0][0]
            assert scoped.judge.model == MODEL_CHOICES[1][0]
            assert scoped.judge is not scoped.model
            assert scoped.resource_root == options["resource_root"]

    asyncio.run(scenario())
    assert "test-only-key" not in repr(environment)


@pytest.mark.parametrize(
    "invalid",
    [
        {"identity_id": None},
        {"court": " "},
        {"topic": {}},
        {"model": "https://untrusted.example/model"},
        {"model": "bedrock_mantle/anthropic.claude-haiku-4-5"},
        {"model": []},
        {"judge": " "},
        {"judge": "https://untrusted.example/judge"},
        {"judge": []},
        {"api_key": None},
        {"api_key": " "},
        {"resource_root": None},
        {"resource_root": " "},
        {"resource_root": []},
        {"resource_root": "private\0path"},
    ],
)
def test_invalid_resolved_options_fail_during_initialization(invalid):
    with pytest.raises(AgentValidationError):
        create_environment(
            **(
                environment_options()
                | {
                    k: v if k in {"court", "topic"} else Mock(return_value=v)
                    for k, v in invalid.items()
                }
            )
        )


@pytest.mark.parametrize(
    "field", ["identity_id", "model", "judge", "api_key", "resource_root"]
)
def test_async_and_failed_callbacks_are_rejected_without_leaking_errors(field):
    async def asynchronous():
        return "test-key"

    with pytest.raises(AgentValidationError, match="synchronously"):
        create_environment(**(environment_options() | {field: asynchronous}))
    with pytest.raises(
        AgentValidationError, match=f"Unable to resolve {field}"
    ) as error:
        create_environment(
            **(
                environment_options()
                | {field: Mock(side_effect=RuntimeError("private secret"))}
            )
        )
    assert "private secret" not in str(error.value)


def test_scope_binding_rejects_another_identity():
    environment = create_environment(**environment_options())
    intruder = AccessContext(identity_id="another-identity")

    async def scenario():
        with pytest.raises(AgentAccessError):
            await environment.scope_factory.bind(
                access=intruder, scope=Scope(court="court", topic="topic")
            )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "court,topic",
    [(None, None), ("court", None), (None, "topic"), ("court", "topic")],
)
def test_scope_strings_are_optional_at_construction(court, topic):
    environment = create_environment(
        **(environment_options() | {"court": court, "topic": topic})
    )
    assert environment.scope == ScopeSelection(court=court, topic=topic)


@pytest.mark.parametrize("field", ["court", "topic"])
def test_scope_callbacks_are_rejected_without_being_called(field):
    callback = Mock(return_value="scope")
    with pytest.raises(AgentValidationError):
        create_environment(**(environment_options() | {field: callback}))
    callback.assert_not_called()


@pytest.mark.parametrize(
    "judge_options", [{}, {"judge": None}, {"judge": lambda: None}]
)
def test_unset_judge_reuses_the_primary_model(judge_options):
    model = Mock(return_value=MODEL_CHOICES[0][0])
    environment = create_environment(
        **(environment_options() | {"model": model} | judge_options)
    )
    scoped = asyncio.run(
        environment.scope_factory.bind(
            access=environment.access,
            scope=Scope(court="court", topic="topic"),
        )
    )
    assert scoped.judge is scoped.model
    model.assert_called_once_with()


def test_resource_root_is_captured_before_the_working_directory_changes(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    environment = create_environment(
        **(environment_options() | {"resource_root": "corpus-root"})
    )
    monkeypatch.chdir(tmp_path.parent)
    scoped = asyncio.run(
        environment.scope_factory.bind(
            access=environment.access,
            scope=Scope(court="court", topic="topic"),
        )
    )
    assert scoped.resource_root == Path(tmp_path) / "corpus-root"
