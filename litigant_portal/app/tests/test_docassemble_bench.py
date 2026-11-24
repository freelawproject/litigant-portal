"""Tests for the docassemble bench script, scripts/docassemble_bench.py.

All tests are DB-free and run in the fast suite. The Docker test image
ships without scripts/, so the module is skipped there.
"""

import json
import tomllib
import zipfile

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


# package


@pytest.fixture
def eviction(tmp_path):
    folder = tmp_path / "fc-eviction"
    folder.mkdir()
    for name in (
        "answer.yml",
        "answer.pdf",
        "lp-branding.css",
        "lp-logo.svg",
        "personas.yml",
        "README.md",
    ):
        (folder / name).write_text(name)
    return folder


def _built(eviction, tmp_path, version="1.0.20261124"):
    path = bench._package(eviction, version, tmp_path / "dist")
    archive = zipfile.ZipFile(path)
    return {
        name: archive.read(name).decode()
        for name in archive.namelist()
        if not name.endswith("/")
    }


def test_package_routes_each_file_into_its_data_folder(eviction, tmp_path):
    root = "docassemble-fceviction/"
    data = root + "docassemble/fceviction/data/"

    assert set(_built(eviction, tmp_path)) == {
        root + "pyproject.toml",
        root + "MANIFEST.in",
        root + "docassemble/fceviction/__init__.py",
        data + "questions/answer.yml",
        data + "templates/answer.pdf",
        data + "static/lp-branding.css",
        data + "static/lp-logo.svg",
    }


def test_package_carries_the_file_contents(eviction, tmp_path):
    files = _built(eviction, tmp_path)

    assert (
        files[
            "docassemble-fceviction/docassemble/fceviction/data/questions/answer.yml"
        ]
        == "answer.yml"
    )


def test_package_is_named_and_versioned_for_docassemble(eviction, tmp_path):
    files = _built(eviction, tmp_path, version="1.0.42")

    project = tomllib.loads(files["docassemble-fceviction/pyproject.toml"])
    init = files["docassemble-fceviction/docassemble/fceviction/__init__.py"]
    assert project["project"]["name"] == "docassemble.fceviction"
    assert project["project"]["version"] == "1.0.42"
    assert init == "__version__ = '1.0.42'\n"


def test_package_ships_the_data_folder_as_package_data(eviction, tmp_path):
    files = _built(eviction, tmp_path)

    manifest = files["docassemble-fceviction/MANIFEST.in"].splitlines()
    assert "graft docassemble/fceviction/data" in manifest


# deploy: _target


def test_target_bench_reads_the_local_bench_settings():
    env = {"DOCASSEMBLE_PUBLIC_URL": "http://bench/", "DA_ADMIN_API_KEY": "k"}

    assert bench._target(env, "bench") == ("http://bench", "k")


@pytest.fixture
def targets(tmp_path):
    path = tmp_path / "targets.yml"
    path.write_text(
        "qa:\n"
        "  url: https://qa.example/interview/\n"
        "  secret: k8s/qa/docassemble-env\n"
        "  region: us-west-2\n"
        "keyless:\n"
        "  url: https://keyless.example\n"
    )
    return path


def _named(targets, name="qa", environ=None, secret=None):
    reads = []

    def read_secret(secret_id, region):
        reads.append((secret_id, region))
        return secret or {}

    target = bench._target(
        {"DA_ADMIN_API_KEY": "bench-key"},
        name,
        targets_file=targets,
        environ=environ or {},
        read_secret=read_secret,
    )
    return target, reads


def test_target_reads_the_key_from_the_instances_aws_secret(targets):
    target, reads = _named(targets, secret={"DA_ADMIN_API_KEY": "qa-key"})

    assert target == ("https://qa.example/interview", "qa-key")
    assert reads == [("k8s/qa/docassemble-env", "us-west-2")]


def test_target_key_from_the_environment_skips_aws(targets):
    target, reads = _named(targets, environ={"DA_API_KEY": "override"})

    assert target == ("https://qa.example/interview", "override")
    assert reads == []


def test_target_secret_without_the_admin_key_names_what_it_holds(targets):
    with pytest.raises(SystemExit) as stopped:
        _named(targets, secret={"DAHOSTNAME": "qa.example", "OTHER": "x"})

    message = str(stopped.value)
    assert "DA_ADMIN_API_KEY" in message
    assert "DAHOSTNAME" in message
    assert "qa.example" not in message


def test_target_with_no_secret_needs_the_key_in_the_environment(targets):
    with pytest.raises(SystemExit, match="DA_API_KEY"):
        _named(targets, name="keyless")


def test_target_unknown_names_the_known_targets(targets):
    with pytest.raises(SystemExit, match="bench, keyless, qa"):
        _named(targets, name="nope")


# deploy: _aws_secret


class _Ran:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_aws_secret_reads_the_secret_json_with_the_aws_cli():
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return _Ran(stdout='{"DA_ADMIN_API_KEY": "k"}\n')

    assert bench._aws_secret("k8s/qa/env", "us-west-2", run=run) == {
        "DA_ADMIN_API_KEY": "k"
    }
    assert calls == [
        [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            "k8s/qa/env",
            "--region",
            "us-west-2",
            "--query",
            "SecretString",
            "--output",
            "text",
        ]
    ]


def test_aws_secret_failure_shows_the_cli_error():
    def run(command, **kwargs):
        return _Ran(returncode=255, stderr="AccessDeniedException: nope")

    with pytest.raises(SystemExit, match="AccessDeniedException"):
        bench._aws_secret("k8s/qa/env", "us-west-2", run=run)


# deploy: _install and _await_install


class _FakeServer:
    """Answers requests in order; the last answer repeats."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def _request(self, method, path, *, query=None, data=None, headers=None):
        self.requests.append((method, path, query))
        answer = (
            self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        )
        if isinstance(answer, BaseException):
            raise answer
        status, payload = answer
        return status, json.dumps(payload).encode()

    def post_form(self, path, fields, files=()):
        self.posted = (path, fields, list(files))
        return self._request("POST", path)


def test_install_uploads_the_zip_and_returns_the_task(tmp_path):
    zip_path = tmp_path / "docassemble-fceviction.zip"
    server = _FakeServer((200, {"task_id": "abc"}))

    assert bench._install(server, zip_path) == "abc"
    assert server.posted == ("/api/package", {}, [("zip", zip_path)])


def test_install_refused_shows_the_servers_reason(tmp_path):
    server = _FakeServer((403, "You do not have permission"))

    with pytest.raises(SystemExit, match="403.*You do not have permission"):
        bench._install(server, tmp_path / "p.zip")


def _wait(server, timeout=60):
    return bench._await_install(
        server, "abc", timeout=timeout, interval=1, sleep=lambda _s: None
    )


def test_await_install_returns_the_log_once_the_install_succeeds():
    server = _FakeServer(
        (200, {"status": "working"}),
        (200, {"status": "completed", "ok": True, "log": "installed"}),
    )

    assert _wait(server) == "installed"
    assert server.requests[-1] == (
        "GET",
        "/api/package_update_status",
        {"task_id": "abc"},
    )


def test_await_install_waits_through_the_server_restart():
    server = _FakeServer(
        bench.BenchUnreachable("down"),
        (502, "Bad Gateway"),
        (200, {"status": "completed", "ok": True, "log": "installed"}),
    )

    assert _wait(server) == "installed"


def test_await_install_fails_with_docassembles_error():
    server = _FakeServer(
        (
            200,
            {"status": "completed", "ok": False, "error_message": "bad yaml"},
        )
    )

    with pytest.raises(SystemExit, match="bad yaml"):
        _wait(server)


def test_await_install_fails_when_the_task_is_unknown():
    server = _FakeServer((200, {"status": "unknown"}))

    with pytest.raises(SystemExit, match="unknown"):
        _wait(server)


def test_await_install_gives_up_after_the_timeout():
    server = _FakeServer((200, {"status": "working"}))

    with pytest.raises(SystemExit, match="still installing"):
        _wait(server, timeout=3)
    assert len(server.requests) == 3


def test_await_install_fails_on_a_refused_status_check():
    server = _FakeServer((403, "Access denied."))

    with pytest.raises(SystemExit, match="403.*Access denied"):
        _wait(server)
