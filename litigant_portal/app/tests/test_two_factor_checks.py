"""The staff two-factor system check. DB-free."""

import pytest

from litigant_portal.app.checks.two_factor import (
    check_staff_two_factor,
    check_two_factor_key,
)


@pytest.mark.parametrize(
    ("required", "debug", "ids"),
    [
        (False, False, ["two_factor.W001"]),
        (False, True, []),
        (True, False, []),
        (True, True, []),
    ],
    ids=["off-outside-debug", "off-in-debug", "on", "on-in-debug"],
)
def test_warns_only_when_the_rule_is_off_outside_debug(
    settings, required, debug, ids
):
    settings.STAFF_TWO_FACTOR_REQUIRED = required
    settings.DEBUG = debug

    assert [w.id for w in check_staff_two_factor(None)] == ids


@pytest.mark.parametrize(
    ("two_factor_key", "debug", "ids"),
    [
        ("secret", False, ["two_factor.W002"]),
        ("secret", True, []),
        ("its-own-key", False, []),
    ],
    ids=["shares-secret-key", "shares-secret-key-in-debug", "own-key"],
)
def test_warns_when_the_key_is_secret_key_outside_debug(
    settings, two_factor_key, debug, ids
):
    settings.SECRET_KEY = "secret"
    settings.TWO_FACTOR_KEY = two_factor_key
    settings.DEBUG = debug

    assert [w.id for w in check_two_factor_key(None)] == ids
