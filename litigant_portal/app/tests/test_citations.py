"""DB-free tests for the citation id grammar and the unknown-id check.

The example ids are the same list the JavaScript chip tests use
(tests/js/chat_engine_markdown.test.cjs), so a grammar change on one side
that is not copied to the other fails a test.
"""

import pytest

from litigant_portal.agents.citations import (
    citation_ids,
    citation_ids_unknown,
)

VALID_IDS = ["court/clerk", "adult-name-change/standard/filing_fee"]
INVALID_IDS = ["Filing_Fee", "a", "a/b/c/d", "nd.courts.gov"]


def _marked(ids):
    return " ".join(f"claim [source:{i}]" for i in ids)


def test_citation_ids_finds_valid_ids_in_order_each_once():
    text = _marked(VALID_IDS + [VALID_IDS[0]])
    assert citation_ids(text) == VALID_IDS


@pytest.mark.parametrize("id", INVALID_IDS)
def test_citation_ids_skips_ids_outside_the_grammar(id):
    assert citation_ids(_marked([id])) == []


def test_citation_ids_is_empty_for_text_without_markers():
    assert citation_ids("Hello [like this] and [source: court/clerk]") == []


def test_unknown_ids_are_those_not_in_the_known_set_in_order():
    text = _marked(["court/ghost", *VALID_IDS, "eviction/tenant/nope"])
    assert citation_ids_unknown(text, VALID_IDS) == [
        "court/ghost",
        "eviction/tenant/nope",
    ]


def test_no_unknown_ids_when_every_id_is_known():
    assert citation_ids_unknown(_marked(VALID_IDS), set(VALID_IDS)) == []


def test_no_unknown_ids_for_text_without_markers():
    assert citation_ids_unknown("Hello.", []) == []


@pytest.mark.parametrize("id", INVALID_IDS)
def test_a_malformed_marker_is_unknown_even_if_listed_as_known(id):
    assert citation_ids_unknown(_marked([id]), [id]) == [id]


def test_a_marker_with_a_space_is_unknown():
    assert citation_ids_unknown(
        "claim [source: court/clerk]", ["court/clerk"]
    ) == [" court/clerk"]
