"""CorpusLoader tests — parsing, error wrapping, and id cross-references."""

import copy
from pathlib import Path

import pytest
import yaml

from litigant_portal.app.topic_flow.loader import (
    CorpusLoader,
    CorpusValidationError,
)
from litigant_portal.app.topic_flow.schema import ResourcesOutput

CONTENT = Path(__file__).resolve().parents[2] / "content"
FIXTURE = CONTENT / "_test_fixture.yml"

# A minimal schema-valid corpus: one fact_gather question, no deadlines or
# outputs. Tests deep-copy and mutate this to introduce specific problems.
VALID = {
    "metadata": {"court": "c", "topic": "t", "role": "r", "title": "T"},
    "sections": [
        {
            "kind": "fact_gather",
            "id": "fg",
            "questions": [{"id": "pubdate", "label": "When"}],
        }
    ],
}


def _write(tmp_path, data):
    path = tmp_path / "corpus.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _write_text(tmp_path, text):
    path = tmp_path / "corpus.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_valid_fixture():
    corpus = CorpusLoader.load(FIXTURE)
    assert corpus.metadata.topic == "test_topic"
    assert len(corpus.sections) == 7


def test_missing_file_raises_with_path(tmp_path):
    missing = tmp_path / "nope.yml"
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(missing)
    assert exc.value.path == missing


def test_bad_yaml_raises(tmp_path):
    path = _write_text(tmp_path, "metadata: {court: c\n bad: : :")
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("YAML parse error" in p for p in exc.value.problems)


def test_non_mapping_top_level_raises(tmp_path):
    path = _write_text(tmp_path, "- one\n- two\n")
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("mapping" in p for p in exc.value.problems)


def test_schema_violation_is_wrapped(tmp_path):
    # Missing metadata + empty sections — a Pydantic error, surfaced as ours.
    path = _write(tmp_path, {"sections": []})
    with pytest.raises(CorpusValidationError):
        CorpusLoader.load(path)


def test_offset_from_must_reference_a_question(tmp_path):
    data = copy.deepcopy(VALID)
    data["deadlines"] = [
        {"id": "d1", "label": "L", "offset_days": 7, "offset_from": "ghost"}
    ]
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("offset_from" in p and "ghost" in p for p in exc.value.problems)


def test_ics_output_unknown_deadline(tmp_path):
    data = copy.deepcopy(VALID)
    data["sections"].append(
        {
            "kind": "output",
            "output_type": "ics",
            "id": "o",
            "heading": "H",
            "deadline_ids": ["ghost"],
        }
    )
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("unknown deadline 'ghost'" in p for p in exc.value.problems)


def test_vcf_output_unknown_contact(tmp_path):
    data = copy.deepcopy(VALID)
    data["sections"].append(
        {
            "kind": "output",
            "output_type": "vcf",
            "id": "o",
            "heading": "H",
            "contact_ids": ["ghost"],
        }
    )
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("unknown contact 'ghost'" in p for p in exc.value.problems)


def test_duplicate_contact_id_detected(tmp_path):
    data = copy.deepcopy(VALID)
    data["contacts"] = [{"id": "dup", "name": "A"}, {"id": "dup", "name": "B"}]
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("duplicate contact id: 'dup'" in p for p in exc.value.problems)


def test_resources_output_unknown_resource(tmp_path):
    data = copy.deepcopy(VALID)
    data["sections"].append(
        {
            "kind": "output",
            "output_type": "resources",
            "id": "o",
            "heading": "H",
            "resource_ids": ["ghost"],
        }
    )
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("unknown resource 'ghost'" in p for p in exc.value.problems)


def test_duplicate_resource_id_detected(tmp_path):
    data = copy.deepcopy(VALID)
    data["resources"] = [
        {"id": "dup", "label": "A", "url": "https://ex/a"},
        {"id": "dup", "label": "B", "url": "https://ex/b"},
    ]
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("duplicate resource id: 'dup'" in p for p in exc.value.problems)


def _packet(**extra):
    return {
        "kind": "output",
        "output_type": "packet",
        "id": "packet",
        "heading": "H",
        "forms": ["Petition"],
        **extra,
    }


def test_prefill_key_must_reference_a_question(tmp_path):
    data = copy.deepcopy(VALID)
    data["sections"].append(
        _packet(
            interview_reference="docassemble.pkg:data/questions/i.yml",
            interview_prefill={"ghost": "current_first"},
        )
    )
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any(
        "prefills 'ghost'" in p and "fact_gather question id" in p
        for p in exc.value.problems
    )


def test_prefill_without_an_interview_reference_is_rejected(tmp_path):
    data = copy.deepcopy(VALID)
    data["sections"].append(
        _packet(interview_prefill={"pubdate": "publication_date"})
    )
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    assert any("no interview_reference" in p for p in exc.value.problems)


def test_packet_without_a_prefill_mapping_still_loads(tmp_path):
    data = copy.deepcopy(VALID)
    data["sections"].append(
        _packet(interview_reference="docassemble.pkg:data/questions/i.yml")
    )
    corpus = CorpusLoader.load(_write(tmp_path, data))
    assert corpus.sections[-1].interview_prefill == {}


def test_problems_aggregate_into_one_error(tmp_path):
    data = copy.deepcopy(VALID)
    data["deadlines"] = [
        {"id": "d1", "label": "L", "offset_days": 7, "offset_from": "ghostq"}
    ]
    data["sections"].append(
        {
            "kind": "output",
            "output_type": "ics",
            "id": "o",
            "heading": "H",
            "deadline_ids": ["ghostd"],
        }
    )
    path = _write(tmp_path, data)
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(path)
    problems = exc.value.problems
    assert any("ghostq" in p for p in problems)
    assert any("ghostd" in p for p in problems)
    assert len(problems) >= 2


# --- when cross-checks (#970 rules POC) -------------------------------------
# A gate may only name a question declared earlier in the corpus, and may only
# compare a choice question against one of its choices.


def _gated_corpus(*sections, deadlines=None):
    data = {
        "metadata": {"court": "c", "topic": "t", "role": "r", "title": "T"},
        "sections": [
            {
                "kind": "fact_gather",
                "id": "who",
                "questions": [
                    {
                        "id": "poc_path",
                        "label": "Role",
                        "type": "choice",
                        "choices": ["renter", "marina"],
                    }
                ],
            },
            *sections,
        ],
    }
    if deadlines is not None:
        data["deadlines"] = deadlines
    return data


def _info(id, when):
    return {
        "kind": "info",
        "id": id,
        "heading": "H",
        "body": "B",
        "when": when,
    }


def test_when_on_a_section_names_an_earlier_question(tmp_path):
    data = _gated_corpus(
        _info("steps", {"fact": "poc_path", "equals": "renter"})
    )
    corpus = CorpusLoader.load(_write(tmp_path, data))
    assert corpus.sections[1].when.equals == "renter"


def test_when_naming_an_unknown_fact_is_a_problem(tmp_path):
    data = _gated_corpus(_info("steps", {"fact": "ghost", "equals": "x"}))
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "section 'steps' when" in p and "'ghost'" in p
        for p in exc.value.problems
    )


def test_when_naming_a_later_question_is_a_problem(tmp_path):
    data = _gated_corpus(
        _info("early", {"fact": "later_q", "answered": True}),
        {
            "kind": "fact_gather",
            "id": "later",
            "questions": [{"id": "later_q", "label": "L"}],
        },
    )
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "section 'early' when" in p and "'later_q'" in p
        for p in exc.value.problems
    )


def test_a_question_when_sees_earlier_questions_of_its_own_section(tmp_path):
    data = _gated_corpus(
        {
            "kind": "fact_gather",
            "id": "notice",
            "questions": [
                {
                    "id": "received",
                    "label": "R",
                    "type": "choice",
                    "choices": ["yes", "no"],
                },
                {
                    "id": "notice_date",
                    "label": "D",
                    "type": "date",
                    "when": {"fact": "received", "equals": "yes"},
                },
            ],
        }
    )
    corpus = CorpusLoader.load(_write(tmp_path, data))
    assert corpus.sections[1].questions[1].when.fact == "received"


def test_a_question_when_may_not_name_itself_or_a_later_sibling(tmp_path):
    data = _gated_corpus(
        {
            "kind": "fact_gather",
            "id": "notice",
            "questions": [
                {
                    "id": "notice_date",
                    "label": "D",
                    "when": {"fact": "received", "answered": True},
                },
                {"id": "received", "label": "R"},
            ],
        }
    )
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "question 'notice_date' when" in p and "'received'" in p
        for p in exc.value.problems
    )


@pytest.mark.parametrize(
    "when",
    [
        {"fact": "poc_path", "equals": "neighbor"},
        {"fact": "poc_path", "not_equals": "neighbor"},
        {"fact": "poc_path", "in": ["renter", "neighbor"]},
        {"all": [{"fact": "poc_path", "equals": "neighbor"}]},
    ],
    ids=["equals", "not-equals", "in", "nested"],
)
def test_a_value_outside_a_choice_list_is_a_problem(tmp_path, when):
    data = _gated_corpus(_info("steps", when))
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "'neighbor' is not a choice of 'poc_path'" in p
        for p in exc.value.problems
    )


def test_a_text_question_accepts_any_compared_value(tmp_path):
    data = _gated_corpus(
        {
            "kind": "fact_gather",
            "id": "name",
            "questions": [{"id": "county", "label": "County"}],
        },
        _info("steps", {"fact": "county", "equals": "Cass"}),
    )
    corpus = CorpusLoader.load(_write(tmp_path, data))
    assert corpus.sections[2].when.equals == "Cass"


def test_a_packet_form_when_is_checked(tmp_path):
    data = _gated_corpus(
        {
            "kind": "output",
            "output_type": "packet",
            "id": "forms",
            "heading": "H",
            "forms": [
                {"name": "Answer", "when": {"fact": "ghost", "equals": "x"}}
            ],
        }
    )
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "output 'forms' form 'Answer' when" in p and "'ghost'" in p
        for p in exc.value.problems
    )


def test_a_deadline_when_may_name_any_question(tmp_path):
    # Deadlines are corpus-level and resolve after every section, so corpus
    # order does not constrain them.
    data = _gated_corpus(
        {
            "kind": "fact_gather",
            "id": "dates",
            "questions": [{"id": "notice_date", "label": "D", "type": "date"}],
        },
        deadlines=[
            {
                "id": "answer_due",
                "label": "Due",
                "offset_days": 14,
                "offset_from": "notice_date",
                "when": {"fact": "poc_path", "equals": "renter"},
            }
        ],
    )
    corpus = CorpusLoader.load(_write(tmp_path, data))
    assert corpus.deadlines[0].when.fact == "poc_path"


def test_a_deadline_when_naming_an_unknown_fact_is_a_problem(tmp_path):
    data = _gated_corpus(
        deadlines=[
            {
                "id": "answer_due",
                "label": "Due",
                "offset_days": 14,
                "offset_from": "poc_path",
                "when": {"fact": "ghost", "answered": True},
            }
        ],
    )
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "deadline 'answer_due' when" in p and "'ghost'" in p
        for p in exc.value.problems
    )


def test_the_poc_corpus_loads():
    corpus = CorpusLoader.load(CONTENT / "harbor-county-boat-slip.yml")
    assert corpus.metadata.court == "harbor-county"
    gated = [s.id for s in corpus.sections if s.when is not None]
    assert gated == [
        "screener",
        "renter_notice",
        "renter_steps",
        "marina_steps",
        "neighbor_steps",
        "answer_urgent",
    ]


# --- screener (#970 rules POC) ----------------------------------------------
# A screener's ``fact`` is an earlier choice question and each outcome value
# one of its choices; its outcomes may read the screener's own questions.


def _screener(fact="poc_path", outcome_value="renter", **extra):
    return {
        "kind": "screener",
        "id": "screener",
        "fact": fact,
        "questions": [
            {
                "id": "pays_fee",
                "label": "Who pays?",
                "type": "choice",
                "choices": ["i_pay", "nobody"],
            }
        ],
        "outcomes": [
            {
                "value": outcome_value,
                "label": "Continue",
                "when": {"fact": "pays_fee", "equals": "i_pay"},
            }
        ],
        **extra,
    }


def test_a_screener_loads_and_its_outcomes_see_its_own_questions(tmp_path):
    corpus = CorpusLoader.load(_write(tmp_path, _gated_corpus(_screener())))
    screener = corpus.sections[1]
    assert screener.kind == "screener"
    assert screener.outcomes[0].when.fact == "pays_fee"


def test_a_screener_question_is_declared_for_later_gates(tmp_path):
    data = _gated_corpus(
        _screener(), _info("after", {"fact": "pays_fee", "equals": "nobody"})
    )
    corpus = CorpusLoader.load(_write(tmp_path, data))
    assert corpus.sections[2].when.fact == "pays_fee"


def test_a_screener_outcome_value_outside_the_facts_choices_is_a_problem(
    tmp_path,
):
    data = _gated_corpus(_screener(outcome_value="neighbor"))
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "screener 'screener' outcome 'neighbor' is not a choice of 'poc_path'"
        in p
        for p in exc.value.problems
    )


@pytest.mark.parametrize(
    "fact",
    ["ghost", "pays_fee"],
    ids=["unknown", "its-own-question"],
)
def test_a_screener_fact_must_be_an_earlier_question(tmp_path, fact):
    data = _gated_corpus(_screener(fact=fact))
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        f"screener 'screener' fact {fact!r} is not a question declared "
        "earlier" in p
        for p in exc.value.problems
    )


def test_a_screener_fact_must_be_a_choice_question(tmp_path):
    data = _gated_corpus(
        {
            "kind": "fact_gather",
            "id": "name",
            "questions": [{"id": "county", "label": "County"}],
        },
        _screener(fact="county", outcome_value="Cass"),
    )
    with pytest.raises(CorpusValidationError) as exc:
        CorpusLoader.load(_write(tmp_path, data))
    assert any(
        "screener 'screener' fact 'county' is not a choice" in p
        for p in exc.value.problems
    )


# The cross-reference and schema tests above run against tmp_path fixtures; this
# one loads the real shipped ND corpora so a typo'd resource_id (or any dangling
# reference) in the live YAML fails CI, not just at runtime. Loading succeeds
# only if every id-reference resolves, so a clean load is itself the assertion.
@pytest.mark.parametrize(
    "name",
    ["adult-name-change-standard.yml", "adult-name-change-waiver.yml"],
)
def test_real_nd_corpus_loads_and_wires_its_resources(name):
    corpus = CorpusLoader.load(CONTENT / name)
    outputs = [s for s in corpus.sections if isinstance(s, ResourcesOutput)]
    assert outputs, f"{name} has no resources output section"
    declared = {r.id for r in corpus.resources}
    for out in outputs:
        assert set(out.resource_ids) <= declared
