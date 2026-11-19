import pytest

checker = pytest.importorskip("scripts.check_lp_logger")


@pytest.mark.parametrize(
    "expression",
    [
        'f"Failure {user}"',
        '"Failure {}".format(user)',
        '"Failure %s" % user',
        '"Failure " + user',
        "message",
    ],
)
def test_rejects_dynamic_messages_even_with_sanitization_disabled(expression):
    source = (
        "from litigant_portal.lp_logger import lp_logger as report\n"
        f"report(type=error, msg={expression}, sanitize=False)\n"
    )
    assert len(checker.violations(source)) == 1


@pytest.mark.parametrize(
    "statement, name",
    [
        ("from litigant_portal.lp_logger import lp_logger", "lp_logger"),
        (
            "from litigant_portal.lp_logger import lp_logger as report",
            "report",
        ),
        (
            "import litigant_portal.lp_logger",
            "litigant_portal.lp_logger.lp_logger",
        ),
        ("import litigant_portal.lp_logger as logs", "logs.lp_logger"),
        ("from litigant_portal import lp_logger as logs", "logs.lp_logger"),
    ],
)
def test_import_forms_allow_literals_and_reject_hidden_messages(
    statement, name
):
    source = f'{statement}\n{name}(type=error, msg="Failure at {{time}}")\n{name}(type=error)\n{name}(type=error, msg=None)\n'
    assert checker.violations(source) == []
    assert len(checker.violations(f"{statement}\n{name}(**options)")) == 1
    assert (
        len(
            checker.violations(f"{statement}\n{name}(type=error, msg=message)")
        )
        == 1
    )
