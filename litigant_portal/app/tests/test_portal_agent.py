"""
The host wrapper translates identity and forwards options to the package.
"""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.utils.functional import SimpleLazyObject

from litigant_portal.agent import PortalAgent
from litigant_portal.app.models import UserIdentity
from lp_agent import AgentValidationError, LPAgent
from lp_agent.adapters.environment import create_environment
from lp_agent.tests.helpers import environment_options


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


@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.parametrize(
    "registered,lazy",
    [(True, False), (False, False), (True, True), (False, True)],
)
def test_portal_translates_identity_and_forwards_callbacks_without_host_reads(
    registered, lazy, django_user_model
):
    options = environment_options()
    del options["identity_id"]
    options = {
        name: Mock(return_value=value) for name, value in options.items()
    }
    user = (
        django_user_model.objects.create_user(username="agent-user")
        if registered
        else None
    )
    saved_identity, _ = UserIdentity.objects.get_or_create(
        user=user, defaults={"session_key": "anonymous-session"}
    )
    identity = (
        SimpleLazyObject(lambda: saved_identity) if lazy else saved_identity
    )
    with (
        patch(
            "litigant_portal.agent.create_environment",
            wraps=create_environment,
        ) as factory,
        patch(
            "litigant_portal.app.selectors.agent.agent_scope_choices"
        ) as catalog,
        patch("litigant_portal.app.selectors.site.site_get_model") as site,
        patch.object(
            LPAgent, "__init__", autospec=True, side_effect=LPAgent.__init__
        ) as initialize,
    ):
        agent = PortalAgent(identity=identity, **options)
    factory.assert_called_once_with(identity_id=str(identity.pk), **options)
    assert initialize.call_count == 1
    catalog.assert_not_called()
    site.assert_not_called()
    for callback in options.values():
        callback.assert_called_once_with()
    assert agent.environment.access.identity_id == str(identity.pk)
    assert agent.runtime == "Workers"
    with pytest.raises(NotImplementedError, match="Workers"):
        asyncio.run(agent.run(message="Hello"))


@pytest.mark.parametrize(
    "identity",
    [
        None,
        object(),
        SimpleNamespace(pk=None),
        SimpleNamespace(pk=uuid4()),
        UserIdentity(),
        UserIdentity(pk=uuid4()),
    ],
)
def test_portal_rejects_missing_or_unsaved_identity(identity):
    options = environment_options()
    del options["identity_id"]
    options = {
        name: Mock(return_value=value) for name, value in options.items()
    }
    with pytest.raises(AgentValidationError, match="identity"):
        PortalAgent(identity=identity, **options)
    for callback in options.values():
        callback.assert_not_called()


@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.parametrize("invalid", [{"runtime": "invalid"}, {"court": " "}])
def test_portal_relies_on_package_validation(invalid):
    options = environment_options()
    del options["identity_id"]
    with pytest.raises(AgentValidationError):
        PortalAgent(
            identity=UserIdentity.objects.create(
                session_key="anonymous-session"
            ),
            **(options | invalid),
        )
