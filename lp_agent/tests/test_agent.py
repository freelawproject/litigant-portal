import asyncio
import inspect
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from lp_agent import (
    AgentValidationError,
    LPAgent,
    RunHandle,
    RunLimits,
    ScopedEnvironment,
)
from lp_agent.types import ScopeSelection


def test_configuration_is_fixed_with_documented_defaults(environment):
    agent = LPAgent(environment=environment)
    assert agent.runtime == "Direct"
    assert agent.interrupt_behavior == "reject"
    assert agent.limits == RunLimits(
        max_steps=30, max_active_seconds=300, max_restarts=2
    )
    for name, value in [
        ("runtime", "Workers"),
        ("interrupt_behavior", "steer"),
        ("limits", RunLimits(max_steps=1)),
        ("environment", environment),
    ]:
        with pytest.raises(AttributeError):
            setattr(agent, name, value)
    with pytest.raises(ValidationError):
        agent.limits.max_steps = 1
    with pytest.raises(FrozenInstanceError):
        environment.scope = ScopeSelection(court="another-court")
    assert not hasattr(agent, "set_runtime")


@pytest.mark.parametrize(
    ("runtime", "policy"),
    [
        ("Workers", "reject"),
        ("Workers", "queue"),
        ("Workers", "steer"),
        ("Direct", "queue"),
        ("Direct", "steer"),
    ],
)
def test_unsupported_execution_is_explicitly_unimplemented(
    environment, runtime, policy
):
    agent = LPAgent(
        environment=environment, runtime=runtime, interrupt_behavior=policy
    )
    with pytest.raises(NotImplementedError):
        asyncio.run(agent.run(message="Hello"))
    with pytest.raises(NotImplementedError, match="Run recovery"):
        asyncio.run(agent.get_run("stored-run"))


@pytest.mark.parametrize(
    "options",
    [
        {"runtime": "MCP"},
        {"runtime": "direct"},
        {"interrupt_behavior": "cancel"},
        {"limits": {"max_steps": 0}},
        {"limits": {"max_restarts": -1}},
    ],
)
def test_constructor_rejects_invalid_configuration(environment, options):
    with pytest.raises(AgentValidationError):
        LPAgent(environment=environment, **options)


@pytest.mark.parametrize(
    "run_request",
    [
        {"message": " \n\t"},
        {"message": "Hello", "conversation_id": ""},
        {"message": "Hello", "attachment_ids": ("",)},
        {"message": "Hello", "attachment_ids": "attachment"},
        {"message": {"private": "do not echo this"}},
    ],
)
def test_submission_validation_precedes_runtime(environment, run_request):
    with pytest.raises(AgentValidationError) as error:
        asyncio.run(LPAgent(environment=environment).run(**run_request))
    assert "do not echo this" not in str(error.value)


@pytest.mark.parametrize("run_id", ["", " \n", None, 42])
def test_recovery_validates_identifiers(environment, run_id):
    with pytest.raises(AgentValidationError):
        asyncio.run(LPAgent(environment=environment).get_run(run_id))


def test_mcp_is_a_separate_unimplemented_entry_point(environment):
    with pytest.raises(NotImplementedError, match="MCP exposure"):
        asyncio.run(LPAgent(environment=environment).serve_mcp())


def test_environment_requires_validated_access_and_scope(environment):
    with pytest.raises(AgentValidationError, match="AccessContext"):
        replace(environment, access="unverified")
    with pytest.raises(AgentValidationError, match="ScopeSelection"):
        replace(environment, scope={"court": "court"})
    with pytest.raises(AgentValidationError, match="AgentEnvironment"):
        LPAgent(environment=object())
    with pytest.raises(AgentValidationError, match="full Scope"):
        ScopedEnvironment(
            access=environment.access,
            scope=ScopeSelection(court="court"),
            model=environment.runs,
            corpus=environment.runs,
            documents=environment.runs,
        )


def test_handle_contract_distinguishes_iteration_from_awaiting():
    for name in ["status", "result", "respond", "cancel"]:
        assert inspect.iscoroutinefunction(getattr(RunHandle, name))
    assert not inspect.iscoroutinefunction(RunHandle.events)
    assert RunHandle.run_id.fset is None
    assert RunHandle.conversation_id.fset is None


def test_core_import_and_validation_without_host_dependencies(tmp_path):
    source = dedent(
        """
        import importlib.abc
        import sys

        sys.path.insert(0, sys.argv[1])
        forbidden = {
            "django",
            "litigant_portal",
            "litellm",
            "openai",
            "anthropic",
            "celery",
            "redis",
            "boto3",
            "botocore"
        }

        class BlockHostImports(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path, target=None):
                if fullname.split(".")[0] in forbidden:
                    raise AssertionError(f"Forbidden dependency: {fullname}")

        sys.meta_path.insert(0, BlockHostImports())
        from lp_agent import LPAgent, RunLimits
        from lp_agent.adapters.environment import create_environment
        from lp_agent.tests.test_direct import ScriptedModel, environment_for
        from lp_agent.types import ModelFinished, ModelOutputItem, ModelTextDelta
        from lp_agent.utils.audit import InstructionArtifact
        from lp_agent.types import ModelMessage, ModelRequest, RunRequest, ToolDefinition

        assert RunLimits().max_steps == 30
        request = RunRequest(message="hello")
        assert RunRequest.model_validate_json(request.model_dump_json()) == request
        model = ScriptedModel([
            ModelTextDelta(delta="Hello"),
            ModelOutputItem(item=ModelMessage(role="assistant", content="Hello")),
            ModelFinished(reason="stop"),
        ])
        agent = LPAgent(environment=environment_for(model))
        events = list(agent.stream(message="Hello"))
        assert '"state":"completed"' in events[-1]
        assert model.closed
        model_request = ModelRequest(
            input=(ModelMessage(role="user", content="hello"),),
            tools=(ToolDefinition(
                name="lookup", description="Find guidance",
                parameters={"type": "object", "properties": {},
                            "required": [], "additionalProperties": False},
            ),),
        )
        assert ModelRequest.model_validate_json(model_request.model_dump_json()) == model_request
        assert len(InstructionArtifact.from_request(model_request).content_hash()) == 64
        assert not (forbidden & {name.split(".")[0] for name in sys.modules})
        """
    )
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            source,
            str(Path(__file__).resolve().parents[2]),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
