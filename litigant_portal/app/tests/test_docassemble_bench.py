"""Tests for the docassemble bench script, scripts/docassemble_bench.py.

All tests are DB-free and run in the fast suite. The Docker test image
ships without scripts/, so the module is skipped there.
"""

import json

import pytest

bench = pytest.importorskip("scripts.docassemble_bench")


class _FakeBench:
    """Serves interview screens in order; the last one repeats."""

    def __init__(self, *screens):
        self.screens = list(screens)
        self.posts = []

    def _next(self):
        return (
            self.screens.pop(0) if len(self.screens) > 1 else self.screens[0]
        )

    def get_json(self, path, **_query):
        if path == "/api/session/new":
            return {"session": "s", "secret": "x"}
        return self._next()

    def post_json(self, _path, payload):
        self.posts.append(payload)
        return 200, json.dumps(self._next()).encode()


def _screen(name, *fields, text="A question"):
    return {"questionName": name, "questionText": text, "fields": list(fields)}


ATTORNEY = _screen(
    "attorney",
    {"variable_name": "landlord_has_attorney"},
    {"variable_name": "attorney_name", "show_if_var": "landlord_has_attorney"},
)


# _walk


def test_walk_names_the_missing_field_when_a_screen_comes_back():
    fake = _FakeBench(ATTORNEY)

    with pytest.raises(SystemExit) as stopped:
        bench._walk(fake, "i", "emily", {"landlord_has_attorney": True})

    message = str(stopped.value)
    assert "no answer for attorney_name" in message
    assert "landlord_has_attorney" not in message.split("no answer for")[1]
    assert len(fake.posts) == 1


def test_walk_answers_a_repeated_question_that_asks_for_new_variables():
    fake = _FakeBench(
        _screen("child", {"variable_name": "children[0].name"}),
        _screen("child", {"variable_name": "children[1].name"}),
        {"questionText": '<a href="/uploadedfile/7/answer.pdf">Download</a>'},
    )
    answers = {"children[0].name": "Ana", "children[1].name": "Ben"}

    assert bench._walk(fake, "i", "emily", answers) == "7"
    assert len(fake.posts) == 2


# _selected


@pytest.fixture
def interviews(tmp_path, monkeypatch):
    folder = tmp_path / "nd-name-change"
    folder.mkdir()
    for name in ("petition.yml", "petition.pdf", "personas.yml", "notes.md"):
        (folder / name).write_text("")
    monkeypatch.setattr(bench, "INTERVIEWS", tmp_path)
    return tmp_path


def test_selected_rejects_a_path_that_does_not_exist(interviews):
    with pytest.raises(SystemExit, match="No interview folder"):
        bench._selected([str(interviews / "nope")])


def test_selected_takes_a_folders_uploadable_files_but_not_its_personas(
    interviews,
):
    folder = interviews / "nd-name-change"

    selected = bench._selected([str(folder)])

    assert selected == {
        folder: [folder / "petition.pdf", folder / "petition.yml"]
    }


def test_selected_takes_one_file_when_given_a_file(interviews):
    file = interviews / "nd-name-change" / "petition.yml"

    assert bench._selected([str(file)]) == {file.parent: [file]}


# _api_key and _env


def test_api_key_prefers_the_bench_admin_key():
    env = {"DA_ADMIN_API_KEY": "admin", "DOCASSEMBLE_API_KEY": "lp"}

    assert bench._api_key(env) == "admin"


def test_api_key_falls_back_to_the_key_lp_uses():
    assert bench._api_key({"DOCASSEMBLE_API_KEY": "lp"}) == "lp"


def test_api_key_missing_names_both_variables():
    with pytest.raises(SystemExit) as stopped:
        bench._api_key({})

    assert "DA_ADMIN_API_KEY" in str(stopped.value)
    assert "DOCASSEMBLE_API_KEY" in str(stopped.value)


def test_env_reads_values_and_skips_comments(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "# DA_ADMIN_API_KEY=commented\n"
        "DA_ADMIN_API_KEY='abc=123'\n"
        'DOCASSEMBLE_PUBLIC_URL = "http://bench"\n'
        "not a setting\n"
    )
    monkeypatch.setattr(bench, "REPO", tmp_path)

    assert bench._env() == {
        "DA_ADMIN_API_KEY": "abc=123",
        "DOCASSEMBLE_PUBLIC_URL": "http://bench",
    }


# _optional and _document_link


@pytest.mark.parametrize(
    ("field", "optional"),
    [
        ({"variable_name": "v"}, False),
        ({"variable_name": "v", "required": False}, True),
        ({"variable_name": "v", "show_if_var": "other"}, True),
        ({"variable_name": "v", "show_if_js": {"expression": "x"}}, True),
    ],
)
def test_optional(field, optional):
    assert bench._optional(_screen("q", field), "v") is optional


def test_optional_is_false_for_a_variable_the_screen_does_not_ask():
    assert bench._optional(ATTORNEY, "case_number") is False


@pytest.mark.parametrize(
    ("html", "number"),
    [
        ('<a href="/uploadedfile/12/answer.pdf">', "12"),
        ('<a href="/storedfiledownload/abc/34.pdf">', "34"),
        ('<a href="/interview?i=x">', None),
    ],
)
def test_document_link(html, number):
    assert bench._document_link({"questionText": html}) == number


# _render


def test_render_clears_old_images_even_without_pdftoppm(tmp_path, monkeypatch):
    pdf = tmp_path / "emily-outlined.pdf"
    old = tmp_path / "emily-outlined-1.png"
    old.write_text("")
    monkeypatch.setattr(bench.shutil, "which", lambda _name: None)

    assert bench._render(pdf) == []
    assert not old.exists()
