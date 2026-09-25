"""Postgres tests: the stored-facts section of the assistant's system prompt.

The section is the model's only view of the briefcase: it must list every
answered variable with its review status, vanish when there is nothing to
show, and carry the rules that stop the model re-asking or inventing facts.
"""

import pytest

from litigant_portal.agents.assistant import (
    LitigantAssistant,
    generate_facts_prompt,
)
from litigant_portal.app.models import ChatThread, UserIdentity, Variable
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.topic_flow import variable_answer_set

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]


@pytest.fixture
def identity():
    return UserIdentity.objects.create(session_key="facts-prompt")


@pytest.fixture
def county(identity):
    return Variable.objects.create(name="county", label="County")


def test_answers_listed_with_confirmed_and_unconfirmed_markers(
    identity, county
):
    date_of_birth = Variable.objects.create(
        name="date_of_birth",
        label="Date of birth",
        data_type=VariableDataType.DATE,
    )
    variable_answer_set(
        identity=identity, variable=county, value="Cass", reviewed=True
    )
    variable_answer_set(
        identity=identity, variable=date_of_birth, value="1991-01-31"
    )

    prompt = generate_facts_prompt(identity)

    assert "- county (County): Cass [confirmed]" in prompt
    assert (
        "- date_of_birth (Date of birth): Thursday, January 31, 1991 "
        "[unconfirmed]" in prompt
    )


def test_identity_without_answers_gets_no_facts_section(identity):
    assert generate_facts_prompt(identity) == ""


def test_cleared_answer_is_not_listed(identity, county):
    variable_answer_set(identity=identity, variable=county, value="Cass")
    variable_answer_set(identity=identity, variable=county, value=None)

    assert generate_facts_prompt(identity) == ""


def test_section_carries_the_fact_handling_rules(identity, county):
    variable_answer_set(identity=identity, variable=county, value="Cass")

    prompt = generate_facts_prompt(identity)

    assert "Never re-ask a fact listed here" in prompt
    assert "the user's own statements awaiting their review" in prompt
    assert "save the new value with RecordFact" in prompt
    assert "confirm it rather than re-ask it from scratch" in prompt
    assert "Never invent a fact" in prompt


def test_system_prompt_includes_the_thread_identitys_facts(identity, county):
    variable_answer_set(identity=identity, variable=county, value="Cass")
    thread = ChatThread.objects.create(
        identity=identity, thread_type="user_chat"
    )

    prompt = LitigantAssistant().generate_system_prompt(thread_id=thread.id)

    assert "## Facts the user has already provided" in prompt
    assert "- county (County): Cass [unconfirmed]" in prompt
