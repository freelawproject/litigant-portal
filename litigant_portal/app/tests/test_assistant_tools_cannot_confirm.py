"""Guard: no assistant tool can mark a fact reviewed.

Only a person may set ``reviewed=True``, through the session-authenticated
``/facts/confirm/`` page endpoint, because reviewed answers prefill the
docassemble interview and skip their questions there. An agent tool that
confirms is the design #890 shipped as ``set_fact_confirmation`` and the one
#948 rules out. These tests fail the moment someone adds it back.

DB-free: they read tool schemas and source files only.
"""

import ast
import inspect
import re
from pathlib import Path

import pytest

from litigant_portal.agents.assistant import LitigantAssistant

TOOLS_DIR = Path(inspect.getsourcefile(LitigantAssistant)).parent / "tools"
FORBIDDEN = re.compile(r"reviewed\s*=\s*True|variable_answer_confirm")
# The one write a tool may make: it stores reviewed=False and resets a
# confirmation on rewrite. Anything else from the services module, or any
# ORM write, could set reviewed by a path the regex above does not see
# (``reviewed=flag``, ``.update(reviewed=...)``).
ANSWER_SERVICES = "litigant_portal.app.services.topic_flow"
ALLOWED_SERVICE_NAMES = {"variable_answer_set"}
ORM_WRITE_METHODS = {
    "save",
    "update",
    "update_or_create",
    "bulk_update",
    "bulk_create",
    "get_or_create",
}
WHY = (
    "only a human may confirm a fact; confirmation belongs on a page "
    "endpoint, never in an agent tool"
)


def _tool_sources():
    files = {Path(inspect.getsourcefile(t)) for t in LitigantAssistant.tools}
    files |= set(TOOLS_DIR.glob("*.py"))
    return sorted(files)


def _service_imports(tree) -> list[str]:
    """Names a module pulls from the answer services, plus whole-module
    imports of it (which would put every service in reach)."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == ANSWER_SERVICES:
            names += [alias.name for alias in node.names]
        if isinstance(node, ast.Import):
            names += [
                alias.name
                for alias in node.names
                if alias.name.startswith(ANSWER_SERVICES)
            ]
    return names


def _orm_write_calls(tree) -> list[str]:
    return [
        f"line {node.lineno}: .{node.func.attr}("
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ORM_WRITE_METHODS
    ]


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


@pytest.mark.parametrize("path", _tool_sources(), ids=lambda p: p.name)
def test_a_tool_imports_only_the_unconfirmed_write_from_the_answer_services(
    path,
):
    tree = ast.parse(path.read_text())
    unexpected = set(_service_imports(tree)) - ALLOWED_SERVICE_NAMES
    assert unexpected == set(), f"{WHY}\n{path.name} imports {unexpected}"


@pytest.mark.parametrize("path", _tool_sources(), ids=lambda p: p.name)
def test_a_tool_makes_no_orm_write_of_its_own(path):
    tree = ast.parse(path.read_text())
    hits = _orm_write_calls(tree)
    assert hits == [], f"{WHY}\n{path.name}: " + ", ".join(hits)


def test_the_guard_covers_every_registered_tool():
    assert LitigantAssistant.tools, "the assistant registers no tools"
    for tool in LitigantAssistant.tools:
        assert Path(inspect.getsourcefile(tool)) in _tool_sources()
