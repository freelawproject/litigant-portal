import asyncio
from unittest.mock import Mock

import pytest

from lp_agent import AgentAccessError, AgentValidationError
from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.adapters.catalog import Court
from lp_agent.adapters.environment import create_environment
from lp_agent.types import AccessContext, Choice, Scope


def environment_options():
    return {
        "identity_id": "identity-1",
        "court": "court",
        "topic": "topic",
        "model": MODEL_CHOICES[0][0],
        "api_key": "test-only-key",
        "catalog": (
            Court(
                choice_id="court",
                label="Court",
                topics=(Choice(choice_id="topic", label="Topic"),),
            ),
        ),
    }


def test_callbacks_resolve_once_at_initialization_and_are_not_retained():
    callbacks = {
        name: Mock(return_value=value)
        for name, value in environment_options().items()
    }
    environment = create_environment(**callbacks)
    for callback in callbacks.values():
        callback.assert_called_once_with()
        callback.side_effect = AssertionError("Must not resolve again")

    async def scenario():
        for _ in range(2):
            courts = await environment.catalog.courts(
                access=environment.access
            )
            assert courts[0].choice_id == "court"
            scoped = await environment.scope_factory.bind(
                access=environment.access,
                scope=Scope(court="court", topic="topic"),
            )
            assert scoped.model.model == MODEL_CHOICES[0][0]

    asyncio.run(scenario())
    assert "test-only-key" not in repr(environment)


@pytest.mark.parametrize(
    "invalid",
    [
        {"identity_id": None},
        {"court": " "},
        {"topic": {}},
        {"model": "https://untrusted.example/model"},
        {"model": []},
        {"api_key": None},
        {"api_key": " "},
        {"catalog": [{"private": "private details"}]},
    ],
)
def test_invalid_resolved_options_fail_during_initialization(invalid):
    with pytest.raises(AgentValidationError) as error:
        create_environment(
            **(
                environment_options()
                | {k: Mock(return_value=v) for k, v in invalid.items()}
            )
        )
    assert "private details" not in str(error.value)


def test_async_and_failed_callbacks_are_rejected_without_leaking_errors():
    async def asynchronous():
        return "test-key"

    with pytest.raises(AgentValidationError, match="synchronously"):
        create_environment(
            **(environment_options() | {"api_key": asynchronous})
        )
    with pytest.raises(
        AgentValidationError, match="Unable to resolve api_key"
    ) as error:
        create_environment(
            **(
                environment_options()
                | {"api_key": Mock(side_effect=RuntimeError("private secret"))}
            )
        )
    assert "private secret" not in str(error.value)


def test_catalog_and_bound_services_reject_another_identity():
    environment = create_environment(**environment_options())
    intruder = AccessContext(identity_id="another-identity")

    async def scenario():
        with pytest.raises(AgentAccessError):
            await environment.catalog.courts(access=intruder)
        with pytest.raises(AgentAccessError):
            await environment.catalog.topics(access=intruder, court="court")
        with pytest.raises(AgentAccessError):
            await environment.scope_factory.bind(
                access=intruder, scope=Scope(court="court", topic="topic")
            )

    asyncio.run(scenario())


def test_catalog_rejects_ambiguous_courts_and_topics():
    options = environment_options()
    with pytest.raises(AgentValidationError, match="court IDs"):
        create_environment(**(options | {"catalog": options["catalog"] * 2}))
    court = options["catalog"][0].model_dump()
    court["topics"] *= 2
    with pytest.raises(AgentValidationError, match="input: Invalid value"):
        create_environment(**(options | {"catalog": [court]}))
