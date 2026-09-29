"""Tests for the RecordFact agent tool.

The tool's whole job is persistence, so every test is postgres-marked.
The safety rule under test throughout: nothing the tool writes can land
reviewed=True, and nothing a bad fact does can block its valid siblings.
"""

import pytest

from litigant_portal.agents.tools.record_fact import RecordFact
from litigant_portal.app.models import (
    ChatThread,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.topic_flow import variable_answer_list
from litigant_portal.app.services.topic_flow import variable_answer_set

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

COUNTY_CHOICES = [
    {"value": "cass", "label": "Cass County"},
    {"value": "burleigh", "label": "Burleigh County"},
]


@pytest.fixture
def thread():
    identity = UserIdentity.objects.create(session_key="chat-facts")
    return ChatThread.objects.create(
        identity=identity, thread_type="user_chat"
    )


@pytest.fixture
def county():
    return Variable.objects.create(
        name="county",
        label="County",
        data_type=VariableDataType.CHOICE,
        choices=COUNTY_CHOICES,
    )


@pytest.fixture
def date_of_birth():
    return Variable.objects.create(
        name="date_of_birth",
        label="Date of birth",
        data_type=VariableDataType.DATE,
    )


def test_stated_fact_lands_as_unconfirmed_answer(thread, county):
    output = RecordFact(facts={"county": "burleigh"})(thread_id=thread.id)

    answer = VariableAnswer.objects.get(
        identity=thread.identity, variable=county
    )
    assert answer.value == "burleigh"
    assert answer.reviewed is False
    assert "county" in output.result


def test_hallucinated_reviewed_arg_is_ignored_and_save_stays_unconfirmed(
    thread, county
):
    # extra="allow" keeps the stray argument as an instance attribute; the
    # save stays unconfirmed because __call__ passes a literal
    # reviewed=False and never reads self.reviewed.
    output = RecordFact(facts={"county": "burleigh"}, reviewed=True)(
        thread_id=thread.id
    )

    answer = VariableAnswer.objects.get(
        identity=thread.identity, variable=county
    )
    assert answer.reviewed is False
    assert "unconfirmed" in output.result


def test_confirmed_answer_resaved_drops_back_to_unconfirmed(thread, county):
    variable_answer_set(
        identity=thread.identity,
        variable=county,
        value="cass",
        reviewed=True,
    )

    RecordFact(facts={"county": "burleigh"})(thread_id=thread.id)

    answer = VariableAnswer.objects.get(
        identity=thread.identity, variable=county
    )
    assert answer.value == "burleigh"
    assert answer.reviewed is False


def test_restated_confirmed_answer_keeps_its_confirmation(thread, county):
    variable_answer_set(
        identity=thread.identity,
        variable=county,
        value="cass",
        reviewed=True,
    )

    output = RecordFact(facts={"county": "cass"})(thread_id=thread.id)

    answer = VariableAnswer.objects.get(
        identity=thread.identity, variable=county
    )
    assert answer.reviewed is True
    assert "Already saved, unchanged: county." in output.result
    assert "Saved as" not in output.result
    assert output.refresh_system_prompt is False


def test_restated_unconfirmed_answer_is_not_rewritten(thread, county):
    before = variable_answer_set(
        identity=thread.identity, variable=county, value="cass"
    )

    RecordFact(facts={"county": "cass"})(thread_id=thread.id)

    answer = VariableAnswer.objects.get(pk=before.pk)
    assert answer.reviewed is False
    assert answer.updated_at == before.updated_at


def test_clearing_a_confirmed_answer_drops_its_confirmation(thread, county):
    variable_answer_set(
        identity=thread.identity,
        variable=county,
        value="cass",
        reviewed=True,
    )

    output = RecordFact(facts={"county": None})(thread_id=thread.id)

    answer = VariableAnswer.objects.get(
        identity=thread.identity, variable=county
    )
    assert answer.value is None
    assert answer.reviewed is False
    assert output.render_data["saved"][0]["cleared"] is True


def test_clearing_an_already_cleared_answer_is_unchanged(thread, county):
    variable_answer_set(identity=thread.identity, variable=county, value=None)

    output = RecordFact(facts={"county": None})(thread_id=thread.id)

    assert output.render_data["saved"] == []
    assert [f["name"] for f in output.render_data["unchanged"]] == ["county"]
    assert "Cleared" not in output.result


def test_restated_value_in_other_case_is_validated_not_unchanged(
    thread, county
):
    variable_answer_set(
        identity=thread.identity, variable=county, value="cass"
    )

    output = RecordFact(facts={"county": "Cass"})(thread_id=thread.id)

    assert output.render_data["unchanged"] == []
    assert "county: must be one of" in output.result


def test_unchanged_facts_carry_label_and_display_value(thread, date_of_birth):
    is_adult = Variable.objects.create(
        name="is_adult",
        label="18 or older",
        data_type=VariableDataType.BOOLEAN,
    )
    variable_answer_set(
        identity=thread.identity, variable=date_of_birth, value="1991-01-31"
    )
    variable_answer_set(
        identity=thread.identity, variable=is_adult, value=True
    )

    output = RecordFact(
        facts={"date_of_birth": "1991-01-31", "is_adult": True}
    )(thread_id=thread.id)

    unchanged = output.render_data["unchanged"]
    # Same lazy-proxy trap as saved rows: pin the type, not just the value.
    assert all(type(fact["value"]) is str for fact in unchanged)
    assert unchanged == [
        {
            "name": "date_of_birth",
            "label": "Date of birth",
            "value": "Thursday, January 31, 1991",
        },
        {"name": "is_adult", "label": "18 or older", "value": "Yes"},
    ]


def test_unchanged_fact_does_not_block_sibling_save(
    thread, county, date_of_birth
):
    variable_answer_set(
        identity=thread.identity,
        variable=county,
        value="cass",
        reviewed=True,
    )

    output = RecordFact(
        facts={"county": "cass", "date_of_birth": "1990-01-31"}
    )(thread_id=thread.id)

    assert (
        VariableAnswer.objects.get(
            identity=thread.identity, variable=date_of_birth
        ).value
        == "1990-01-31"
    )
    assert [fact["name"] for fact in output.render_data["saved"]] == [
        "date_of_birth"
    ]
    assert output.refresh_system_prompt is True


def test_unknown_name_reported_without_blocking_sibling_save(thread, county):
    output = RecordFact(facts={"not_a_variable": "x", "county": "cass"})(
        thread_id=thread.id
    )

    assert (
        VariableAnswer.objects.get(
            identity=thread.identity, variable=county
        ).value
        == "cass"
    )
    assert "not_a_variable: no variable with this name" in output.result
    assert "exact variable names" in output.result


def test_invalid_value_reported_without_blocking_sibling_save(
    thread, county, date_of_birth
):
    output = RecordFact(
        facts={"county": "atlantis", "date_of_birth": "1990-01-31"}
    )(thread_id=thread.id)

    assert not VariableAnswer.objects.filter(variable=county).exists()
    assert (
        VariableAnswer.objects.get(
            identity=thread.identity, variable=date_of_birth
        ).value
        == "1990-01-31"
    )
    assert "county: must be one of" in output.result


def test_out_of_schema_variable_treated_as_unknown(thread):
    Variable.objects.create(name="retired_fact", in_schema=False)

    output = RecordFact(facts={"retired_fact": "x"})(thread_id=thread.id)

    assert not VariableAnswer.objects.exists()
    assert "retired_fact: no variable with this name" in output.result


def test_null_value_clears_the_answer(thread, county):
    variable_answer_set(
        identity=thread.identity, variable=county, value="cass"
    )

    output = RecordFact(facts={"county": None})(thread_id=thread.id)

    assert (
        VariableAnswer.objects.get(
            identity=thread.identity, variable=county
        ).value
        is None
    )
    assert (
        variable_answer_list(identity=thread.identity, answered_only=True)
        == []
    )
    assert "Cleared saved answers: county." in output.result
    assert output.render_data["saved"][0]["cleared"] is True


def test_empty_mapping_is_an_error_and_writes_nothing(thread):
    output = RecordFact(facts={})(thread_id=thread.id)

    assert output.result.startswith("Error:")
    assert not VariableAnswer.objects.exists()
    assert output.refresh_system_prompt is False


def test_prompt_refresh_only_when_something_was_written(thread, county):
    saved = RecordFact(facts={"county": "cass"})(thread_id=thread.id)
    failed = RecordFact(facts={"county": "atlantis"})(thread_id=thread.id)

    assert saved.refresh_system_prompt is True
    assert failed.refresh_system_prompt is False


def test_render_data_carries_plain_strings_and_labels(thread):
    Variable.objects.create(
        name="is_adult",
        label="18 or older",
        data_type=VariableDataType.BOOLEAN,
    )

    output = RecordFact(facts={"is_adult": True, "unknown_name": "x"})(
        thread_id=thread.id
    )

    fact = output.render_data["saved"][0]
    # display_value for booleans is a lazy translation proxy that compares
    # equal to its str; the engine's JSON serialization needs a real str,
    # so pin the type, not just the value.
    assert type(fact["value"]) is str
    assert fact == {
        "name": "is_adult",
        "label": "18 or older",
        "value": "Yes",
        "cleared": False,
    }
    assert output.render_data["errors"] == [
        {
            "name": "unknown_name",
            "label": "unknown_name",
            "message": "no variable with this name",
        }
    ]
