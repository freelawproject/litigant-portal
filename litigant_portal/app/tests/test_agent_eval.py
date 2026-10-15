"""Tests for the agent eval harness under scripts/agent_eval.

All tests are DB-free and run in the fast suite.
"""

from scripts.agent_eval.schema import Config, read_cases


def test_every_case_in_cases_yml_loads():
    assert len(read_cases(Config())) > 20
