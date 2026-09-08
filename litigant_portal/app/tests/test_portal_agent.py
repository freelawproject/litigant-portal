"""
The host wrapper translates identity and forwards options to the package.
"""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from litigant_portal.agent import PortalAgent
from lp_agent import AgentValidationError, LPAgent
from lp_agent.adapters.environment import create_environment
from lp_agent.tests.test_environment_factory import environment_options


def test_portal_declares_host_inputs_and_workers_default():
    parameters = inspect.signature(PortalAgent).parameters
    assert parameters["runtime"].default == "Workers"
    for name in ("identity", "model", "api_key", "catalog"):
        assert parameters[name].default is inspect.Parameter.empty
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["court"].default is None
    assert parameters["topic"].default is None
    assert PortalAgent.run is LPAgent.run
    assert PortalAgent.stream is LPAgent.stream
    assert PortalAgent.get_run is LPAgent.get_run


def test_portal_translates_identity_and_forwards_callbacks_without_host_reads():
    options = environment_options()
    del options["identity_id"]
    options = {
        name: Mock(return_value=value) for name, value in options.items()
    }
    identity = SimpleNamespace(pk=uuid4())
    with (
        patch(
            "litigant_portal.agent.create_environment",
            wraps=create_environment,
        ) as factory,
        patch(
            "litigant_portal.app.selectors.agent.agent_scope_choices"
        ) as catalog,
        patch("litigant_portal.app.selectors.site.site_get_model") as site,
    ):
        agent = PortalAgent(identity=identity, **options)
    factory.assert_called_once_with(identity_id=str(identity.pk), **options)
    catalog.assert_not_called()
    site.assert_not_called()
    for callback in options.values():
        callback.assert_called_once_with()
    assert agent.environment.access.identity_id == str(identity.pk)
    assert agent.runtime == "Workers"
    with pytest.raises(NotImplementedError, match="Workers"):
        asyncio.run(agent.run(message="Hello"))


@pytest.mark.parametrize(
    "identity", [None, object(), SimpleNamespace(pk=None)]
)
def test_portal_rejects_missing_or_unsaved_identity(identity):
    options = environment_options()
    del options["identity_id"]
    with pytest.raises(AgentValidationError, match="identity"):
        PortalAgent(identity=identity, **options)


@pytest.mark.parametrize("invalid", [{"runtime": "invalid"}, {"court": " "}])
def test_portal_relies_on_package_validation(invalid):
    options = environment_options()
    del options["identity_id"]
    with pytest.raises(AgentValidationError):
        PortalAgent(
            identity=SimpleNamespace(pk=uuid4()), **(options | invalid)
        )
