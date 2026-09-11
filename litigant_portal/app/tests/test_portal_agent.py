"""
The host wrapper translates identity and forwards options to the package.
"""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.conf import settings
from django.test import override_settings
from django.utils.functional import SimpleLazyObject
from pydantic import SecretStr

from litigant_portal.agent import PortalAgent
from litigant_portal.app.models import UserIdentity
from lp_agent import AgentValidationError
from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.adapters.environment import create_environment
from lp_agent.corpus.file_search import get_file_based_corpus
from lp_agent.types import Scope


def portal_options():
    return {
        "court": "court",
        "topic": "topic",
        "model": MODEL_CHOICES[0][0],
        "judge": MODEL_CHOICES[1][0],
    }


def test_portal_declares_host_inputs_and_workers_default():
    parameters = inspect.signature(PortalAgent).parameters
    assert parameters["runtime"].default == "Workers"
    for name in ("identity", "model"):
        assert parameters[name].default is inspect.Parameter.empty
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["court"].default is None
    assert parameters["topic"].default is None
    assert parameters["judge"].default is None
    assert "catalog" not in parameters
    assert "api_key" not in parameters


@pytest.mark.postgres
@pytest.mark.django_db
@override_settings(BEDROCK_API_KEY="test-only-key")
@pytest.mark.parametrize(
    "registered,lazy",
    [(True, False), (False, False), (True, True), (False, True)],
)
def test_portal_translates_identity_and_forwards_callbacks_and_settings(
    registered, lazy, django_user_model
):
    options = portal_options()
    options = {
        name: value if name in {"court", "topic"} else Mock(return_value=value)
        for name, value in options.items()
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
    with patch(
        "litigant_portal.agent.create_environment", wraps=create_environment
    ) as factory:
        agent = PortalAgent(identity=identity, **options)
    factory.assert_called_once_with(
        identity_id=str(identity.pk),
        api_key=SecretStr("test-only-key"),
        resource_root=settings.BASE_DIR,
        **options,
    )
    for name in ("model", "judge"):
        options[name].assert_called_once_with()
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
    options = portal_options()
    options = {
        name: Mock(return_value=value) for name, value in options.items()
    }
    with pytest.raises(AgentValidationError, match="identity"):
        PortalAgent(identity=identity, **options)
    for callback in options.values():
        callback.assert_not_called()


@pytest.mark.postgres
@pytest.mark.django_db
@override_settings(BEDROCK_API_KEY="test-only-key")
@pytest.mark.parametrize("invalid", [{"runtime": "invalid"}, {"court": " "}])
def test_portal_relies_on_package_validation(invalid):
    options = portal_options()
    with pytest.raises(AgentValidationError):
        PortalAgent(
            identity=UserIdentity.objects.create(
                session_key="anonymous-session"
            ),
            **(options | invalid),
        )


@pytest.mark.postgres
@pytest.mark.django_db
@override_settings(BEDROCK_API_KEY="test-only-key")
def test_portal_resource_root_is_used_for_corpus_retrieval(tmp_path):
    files = {
        "corpus/courts/example/court.yml": "name: Example court\n",
        "corpus/courts/example/topics/task/topic.yml": "title: Example task\n",
    }
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    identity = UserIdentity.objects.create(session_key="corpus-session")
    with override_settings(BASE_DIR=tmp_path):
        agent = PortalAgent(
            identity=identity,
            model=MODEL_CHOICES[0][0],
            court="example",
            topic="task",
        )

    async def retrieve():
        scoped = await agent.environment.scope_factory.bind(
            access=agent.environment.access,
            scope=Scope(court="example", topic="task"),
        )
        assert scoped.judge is scoped.model
        return await get_file_based_corpus(
            scoped.scope.court,
            scoped.scope.topic,
            resource_root=scoped.resource_root,
        )

    documents = asyncio.run(retrieve())
    assert {
        document.source.locator: document.content for document in documents
    } == files
