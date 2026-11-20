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
    "statement, name, package",
    [
        ("from litigant_portal.lp_logger import lp_logger", "lp_logger", ""),
        (
            "from litigant_portal.lp_logger import lp_logger as report",
            "report",
            "",
        ),
        (
            "import litigant_portal.lp_logger",
            "litigant_portal.lp_logger.lp_logger",
            "",
        ),
        ("import litigant_portal.lp_logger as logs", "logs.lp_logger", ""),
        (
            "from litigant_portal import lp_logger as logs",
            "logs.lp_logger",
            "",
        ),
        (
            "from .lp_logger import lp_logger",
            "lp_logger",
            "litigant_portal",
        ),
        (
            "from .lp_logger import lp_logger as report",
            "report",
            "litigant_portal",
        ),
        (
            "from ...lp_logger import lp_logger",
            "lp_logger",
            "litigant_portal.app.views",
        ),
        (
            "from . import lp_logger as logs",
            "logs.lp_logger",
            "litigant_portal",
        ),
    ],
)
def test_import_forms_allow_literals_and_reject_hidden_messages(
    statement, name, package
):
    source = f'{statement}\n{name}(type=error, msg="Failure at {{time}}")\n{name}(type=error)\n{name}(type=error, msg=None)\n'
    assert checker.violations(source, package=package) == []
    assert (
        len(
            checker.violations(
                f"{statement}\n{name}(**options)", package=package
            )
        )
        == 1
    )
    assert (
        len(
            checker.violations(
                f"{statement}\n{name}(type=error, msg=message)",
                package=package,
            )
        )
        == 1
    )


@pytest.mark.parametrize("package", ["", "litigant_portal"])
def test_rejects_unresolvable_relative_imports(package):
    assert checker.violations(
        "from ..lp_logger import lp_logger", package=package
    ) == [(1, "unable to resolve relative import; use an absolute import")]


def test_relative_import_of_unrelated_logger_is_not_checked():
    source = (
        "from .lp_logger import lp_logger\n"
        "lp_logger(type=error, msg=message, **options)\n"
    )
    assert checker.violations(source, package="litigant_portal.app") == []


def test_cli_resolves_package_from_nested_filename(
    tmp_path, monkeypatch, capsys
):
    source = tmp_path / "litigant_portal/app/views/example.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from ...lp_logger import lp_logger\n"
        "lp_logger(type=error, msg=message)\n",
        encoding="utf-8",
    )
    filename = str(source.relative_to(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checker.sys, "argv", ["check_lp_logger.py", filename])
    assert checker.main() == 1
    assert capsys.readouterr().out == (
        f"{filename}:2: lp_logger msg must be a literal string or None\n"
    )
