"""
Keep the temporary shared database option explicit and limited to dev and QA.
"""

import asyncio
import runpy

import pytest
from django.conf import settings
from django.test import override_settings

from lp_agent.adapters.session import (
    DatabaseConnections,
    default_connection_options,
)
from lp_agent.errors import AgentValidationError


@pytest.mark.parametrize(
    "environment,enabled", [("qa", True), ("prod", False), ("dev", False)]
)
def test_agent_flags_default_on_only_for_qa(monkeypatch, environment, enabled):
    monkeypatch.setenv("DEPLOYMENT_ENV", environment)
    monkeypatch.delenv("LP_AGENT_USE_DJANGO_DB", raising=False)
    monkeypatch.delenv("LP_AGENT_DEV_ENABLED", raising=False)
    configured = runpy.run_path(str(settings.BASE_DIR / "settings.py"))
    assert configured["LP_AGENT_USE_DJANGO_DB"] is enabled
    assert configured["LP_AGENT_DEV_ENABLED"] is enabled


@pytest.mark.parametrize(
    "flag", ["LP_AGENT_USE_DJANGO_DB", "LP_AGENT_DEV_ENABLED"]
)
def test_explicit_setting_overrides_qa_default(monkeypatch, flag):
    monkeypatch.setenv("DEPLOYMENT_ENV", "qa")
    monkeypatch.delenv("LP_AGENT_USE_DJANGO_DB", raising=False)
    monkeypatch.delenv("LP_AGENT_DEV_ENABLED", raising=False)
    monkeypatch.setenv(flag, "false")
    configured = runpy.run_path(str(settings.BASE_DIR / "settings.py"))
    assert configured[flag] is False
    other = (
        "LP_AGENT_DEV_ENABLED"
        if flag == "LP_AGENT_USE_DJANGO_DB"
        else "LP_AGENT_USE_DJANGO_DB"
    )
    assert configured[other] is True


@pytest.mark.parametrize("environment", ["prod", "unknown"])
def test_shared_database_is_rejected_outside_dev_and_qa(environment):
    with (
        override_settings(
            DEPLOYMENT_ENV=environment, LP_AGENT_USE_DJANGO_DB=True
        ),
        pytest.raises(
            AgentValidationError, match="only available in dev and QA"
        ),
    ):
        default_connection_options()


def test_explicit_dsns_are_used_when_shared_database_is_off():
    with override_settings(
        LP_AGENT_USE_DJANGO_DB=False,
        LP_AGENT_WRITER_DSN="writer-dsn",
        LP_AGENT_LOOKUP_DSN="lookup-dsn",
        CORPUS_COURT="north-dakota",
    ):
        assert default_connection_options() == {
            "writer": "writer-dsn",
            "lookup": "lookup-dsn",
            "court": "north-dakota",
        }


def test_missing_credentials_still_fail_when_shared_database_is_off():
    async def scenario():
        for lookup in (False, True):
            with pytest.raises(AgentValidationError, match="not configured"):
                async with DatabaseConnections().connection(lookup=lookup):
                    pytest.fail("A database connection should not open")

    with override_settings(
        LP_AGENT_USE_DJANGO_DB=False,
        LP_AGENT_WRITER_DSN="",
        LP_AGENT_LOOKUP_DSN="",
    ):
        asyncio.run(scenario())
