"""Drift guard: the name/county questions the ND flows ask never echo back.

The ND name-change flows collect them for the docassemble prefill, not to
display them. The page protects a field through the glossary's private flag,
so a corpus-side edit that drops the flag would only surface on a shared
terminal. DB-free.
"""

import pytest

from litigant_portal.app.selectors.corpus import (
    corpus_load_flows,
    corpus_load_variables,
)

NAME_CHANGE_FLOWS = [
    ("north-dakota", "adult-name-change", "standard"),
    ("north-dakota", "adult-name-change", "waiver"),
]
IDENTITY_VARIABLES = ["first_name", "middle_name", "last_name", "county"]


def _placed_names(key):
    flow = corpus_load_flows()[key]
    return [name for page in flow.interview for name in page.variables]


@pytest.mark.parametrize("key", NAME_CHANGE_FLOWS, ids=lambda k: k[-1])
@pytest.mark.parametrize("name", IDENTITY_VARIABLES)
def test_name_change_flow_places_the_identity_variable(key, name):
    assert name in _placed_names(key)


@pytest.mark.parametrize("name", IDENTITY_VARIABLES)
def test_identity_variable_is_private_in_the_glossary(name):
    assert corpus_load_variables()[name].is_private
