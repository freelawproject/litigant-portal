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
