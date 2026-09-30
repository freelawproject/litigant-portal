"""Guard: no assistant tool can mark a fact reviewed.

Only a person may set ``reviewed=True``, through the session-authenticated
``/facts/confirm/`` page endpoint, because reviewed answers prefill the
docassemble interview and skip their questions there. An agent tool that
confirms is the design #890 shipped as ``set_fact_confirmation`` and the one
#948 rules out. These tests fail the moment someone adds it back.

DB-free: they read tool schemas and source files only.
"""

import inspect
import re
from pathlib import Path

import pytest

from litigant_portal.agents.assistant import LitigantAssistant

TOOLS_DIR = Path(inspect.getsourcefile(LitigantAssistant)).parent / "tools"
FORBIDDEN = re.compile(r"reviewed\s*=\s*True|variable_answer_confirm")
WHY = (
    "only a human may confirm a fact; confirmation belongs on a page "
    "endpoint, never in an agent tool"
)


def _tool_sources():
    files = {Path(inspect.getsourcefile(t)) for t in LitigantAssistant.tools}
    files |= set(TOOLS_DIR.glob("*.py"))
    return sorted(files)


@pytest.mark.parametrize(
    "tool", LitigantAssistant.tools, ids=lambda t: t.__name__
)
def test_no_tool_schema_exposes_a_reviewed_argument(tool):
    schema = tool.get_schema()["function"]["parameters"]
    properties = schema.get("properties", {})
    assert "reviewed" not in properties, WHY


@pytest.mark.parametrize("path", _tool_sources(), ids=lambda p: p.name)
def test_no_tool_source_can_write_reviewed_true(path):
    hits = [
        f"{path.name}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text().splitlines(), start=1)
        if FORBIDDEN.search(line)
    ]
    assert hits == [], f"{WHY}\n" + "\n".join(hits)


def test_the_guard_covers_every_registered_tool():
    assert LitigantAssistant.tools, "the assistant registers no tools"
    for tool in LitigantAssistant.tools:
        assert Path(inspect.getsourcefile(tool)) in _tool_sources()
