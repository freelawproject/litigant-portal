"""DB-free tests: which tester tools each deployment shows (#1037).

Four tiers come from two settings. QA is the omni-court testing instance,
dev matches it, prod shows nothing, and a pilot is prod plus a tester
layer. Anything unset or unknown falls closed to prod.
"""

import pytest
from django.test import override_settings

from litigant_portal.app.features import (
    GITHUB_FEEDBACK_URL,
    features,
    features_for,
    parse_deployment_env,
    parse_pilot,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("dev", "dev"),
        ("qa", "qa"),
        ("prod", "prod"),
        (None, "prod"),
        ("", "prod"),
        ("production", "prod"),
        ("QA", "prod"),
    ],
    ids=[
        "dev",
        "qa",
        "prod",
        "unset",
        "blank",
        "typo",
        "wrong-case",
    ],
)
def test_unset_or_unknown_deployment_env_falls_closed_to_prod(raw, expected):
    assert parse_deployment_env(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("True", False),
        ("1", False),
        ("", False),
        (None, False),
    ],
    ids=["true", "capitalized", "one", "blank", "unset"],
)
def test_only_the_exact_value_true_turns_pilot_on(raw, expected):
    assert parse_pilot(raw) is expected


# Every tester tool and the layers that get it, from #1037. Additive:
# prod gets nothing, PILOT adds the pilot tools, dev and qa get everything.
PILOT_TOOLS = {
    "build_stamp",
    "start_over",
    "court_user_admin",
    "flow_links",
    "style_guide",
}
FLP_TOOLS = {"court_switcher", "citation_chips"}


@pytest.mark.parametrize(
    ("env", "pilot", "expected"),
    [
        ("prod", False, set()),
        ("prod", True, PILOT_TOOLS),
        ("dev", False, PILOT_TOOLS | FLP_TOOLS),
        ("qa", False, PILOT_TOOLS | FLP_TOOLS),
        ("qa", True, PILOT_TOOLS | FLP_TOOLS),
    ],
    ids=["prod", "pilot", "dev", "qa", "pilot-adds-nothing-on-qa"],
)
def test_each_layer_adds_its_tools(env, pilot, expected):
    result = features_for(env, pilot, feedback_email="lp@example.org")
    enabled = {t for t in PILOT_TOOLS | FLP_TOOLS if getattr(result, t)}
    assert enabled == expected


@pytest.mark.parametrize(
    ("env", "pilot", "label"),
    [
        ("prod", False, ""),
        ("prod", True, "pilot"),
        ("dev", False, "dev"),
        ("qa", False, "qa"),
        ("qa", True, "qa · pilot"),
    ],
    ids=["prod", "pilot", "dev", "qa", "pilot-set-on-qa-shows"],
)
def test_the_stamp_label_reports_the_settings(env, pilot, label):
    assert features_for(env, pilot, feedback_email="").stamp_label == label


@pytest.mark.parametrize(
    ("env", "pilot", "expected"),
    [
        ("dev", False, GITHUB_FEEDBACK_URL),
        ("qa", False, GITHUB_FEEDBACK_URL),
        ("prod", True, "mailto:lp@example.org"),
        ("prod", False, ""),
    ],
    ids=["dev-github", "qa-github", "pilot-email", "prod-none"],
)
def test_pilots_send_feedback_by_email_and_everyone_else_by_github(
    env, pilot, expected
):
    result = features_for(env, pilot, feedback_email="lp@example.org")
    assert result.feedback_url == expected
    assert result.feedback_by_email is expected.startswith("mailto:")
    by_email = expected.startswith("mailto:")
    assert result.feedback_address == ("lp@example.org" if by_email else "")


def test_a_pilot_without_a_feedback_address_shows_no_feedback_link():
    assert features_for("prod", True, feedback_email="").feedback_url == ""


@override_settings(DEPLOYMENT_ENV="prod", PILOT=True, FEEDBACK_EMAIL="x@y.z")
def test_features_reads_the_current_settings():
    result = features()
    assert result.start_over is True
    assert result.feedback_url == "mailto:x@y.z"


@pytest.mark.parametrize(
    ("env", "pilot", "shown"),
    [("prod", False, False), ("prod", True, True), ("dev", False, True)],
    ids=["prod", "pilot", "dev"],
)
def test_the_tester_menu_shows_when_any_of_its_tools_is_on(env, pilot, shown):
    assert features_for(env, pilot, feedback_email="").tester_menu is shown
