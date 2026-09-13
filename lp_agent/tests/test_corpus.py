"""
Corpus retrieval boundaries and temporary file lookup without host dependencies.
"""

import asyncio
import os
from pathlib import Path
from threading import get_ident

import pytest

from lp_agent import AgentValidationError
from lp_agent.corpus.db_search import get_database_corpus
from lp_agent.corpus.file_search import get_file_based_corpus
from lp_agent.corpus.s3_search import get_s3_corpus
from lp_agent.corpus.vec_search import get_vector_corpus


@pytest.fixture
def corpus_root(tmp_path):
    files = {
        "corpus/courts/court/court.yml": "name: Example court\n",
        "corpus/courts/court/topics/topic/topic.yml": "title: Café\n",
        "corpus/courts/court/topics/topic/flows/standard.yml": "name: Standard\n",
        "corpus/courts/court/topics/topic/guidelines/help.yaml": "instructions: Ask for help\n",
        "corpus/courts/court/topics/topic/notes.txt": "Not YAML\n",
        "corpus/courts/court/topics/other/topic.yml": "title: Other topic\n",
        "corpus/courts/other/court.yml": "name: Other court\n",
        "prompts/courts/court/prompt.md": "Legacy guidelines\n",
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "retrieve,options,message",
    [
        (get_database_corpus, {}, "Database corpus retrieval"),
        (get_s3_corpus, {}, "S3 corpus retrieval"),
        (get_vector_corpus, {"query": "help"}, "Vector corpus search"),
    ],
)
def test_backend_functions_report_unimplemented(retrieve, options, message):
    with pytest.raises(NotImplementedError, match=message):
        asyncio.run(retrieve("court", "topic", **options))


@pytest.mark.parametrize("root_type", [str, Path])
def test_file_retrieval_preserves_content_provenance_and_scope(
    corpus_root, root_type
):
    documents = asyncio.run(
        get_file_based_corpus(
            "court", "topic", resource_root=root_type(corpus_root)
        )
    )
    expected = [
        "corpus/courts/court/court.yml",
        "corpus/courts/court/topics/topic/flows/standard.yml",
        "corpus/courts/court/topics/topic/guidelines/help.yaml",
        "corpus/courts/court/topics/topic/topic.yml",
    ]
    assert isinstance(documents, tuple)
    assert [document.source.source_id for document in documents] == expected
    for document, relative in zip(documents, expected, strict=True):
        assert document.content == (corpus_root / relative).read_text(
            encoding="utf-8"
        )
        assert document.source.locator == relative
        assert document.source.kind == "corpus"
        assert document.source.title == Path(relative).name


def test_file_reads_run_off_the_event_loop(corpus_root, monkeypatch):
    caller_thread = get_ident()
    read_text = Path.read_text
    readers = []

    def read_in_worker(path, *args, **kwargs):
        readers.append(get_ident())
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_in_worker)
    asyncio.run(
        get_file_based_corpus("court", "topic", resource_root=corpus_root)
    )
    assert readers
    assert all(reader != caller_thread for reader in readers)


@pytest.mark.parametrize("field", ["court", "topic"])
@pytest.mark.parametrize(
    "key",
    ["", " ", ".", "..", "../other", "/other", "other\\topic", "bad\0key"],
)
def test_scope_keys_cannot_traverse_directories(corpus_root, field, key):
    with pytest.raises(AgentValidationError, match="single path components"):
        asyncio.run(
            get_file_based_corpus(
                **({"court": "court", "topic": "topic"} | {field: key}),
                resource_root=corpus_root,
            )
        )


@pytest.mark.parametrize(
    "court,topic", [("missing", "topic"), ("court", "missing")]
)
def test_unknown_scope_reports_missing_corpus(corpus_root, court, topic):
    with pytest.raises(AgentValidationError, match="No file-based corpus"):
        asyncio.run(
            get_file_based_corpus(court, topic, resource_root=corpus_root)
        )


@pytest.mark.parametrize(
    "relative",
    [
        "corpus/courts/court/court.yml",
        "corpus/courts/court/topics/topic/topic.yml",
    ],
)
def test_missing_metadata_does_not_return_partial_corpus(
    corpus_root, relative
):
    (corpus_root / relative).unlink()
    with pytest.raises(AgentValidationError, match="No file-based corpus"):
        asyncio.run(
            get_file_based_corpus("court", "topic", resource_root=corpus_root)
        )


def test_missing_root_reports_missing_corpus(tmp_path):
    with pytest.raises(AgentValidationError, match="No file-based corpus"):
        asyncio.run(
            get_file_based_corpus(
                "court", "topic", resource_root=tmp_path / "missing"
            )
        )


@pytest.mark.parametrize(
    "relative",
    [
        "corpus/courts/court/court.yml",
        "corpus/courts/court/topics/topic/flows/standard.yml",
    ],
)
def test_symlinked_files_cannot_read_another_scope(corpus_root, relative):
    path = corpus_root / relative
    path.unlink()
    path.symlink_to(corpus_root / "corpus/courts/other/court.yml")
    with pytest.raises(
        AgentValidationError, match="escapes the selected scope"
    ):
        asyncio.run(
            get_file_based_corpus("court", "topic", resource_root=corpus_root)
        )


def test_symlinked_topic_cannot_read_another_scope(corpus_root):
    topics = corpus_root / "corpus/courts/court/topics"
    (topics / "alias").symlink_to(topics / "topic", target_is_directory=True)
    with pytest.raises(
        AgentValidationError, match="escapes the selected scope"
    ):
        asyncio.run(
            get_file_based_corpus("court", "alias", resource_root=corpus_root)
        )


@pytest.mark.parametrize("operation", ["file", "directory"])
def test_unreadable_files_and_directories_report_safe_errors(
    corpus_root, monkeypatch, operation
):
    def denied(*args, **kwargs):
        raise PermissionError("private filesystem details")

    if operation == "file":
        monkeypatch.setattr(Path, "read_text", denied)
    else:
        scandir = os.scandir
        unreadable = corpus_root / "corpus/courts/court/topics/topic/flows"

        def scan_directory(path):
            if Path(path) == unreadable:
                denied()
            return scandir(path)

        monkeypatch.setattr(os, "scandir", scan_directory)
    with pytest.raises(
        AgentValidationError, match="could not be read"
    ) as error:
        asyncio.run(
            get_file_based_corpus("court", "topic", resource_root=corpus_root)
        )
    assert "private filesystem details" not in str(error.value)


def test_invalid_utf8_reports_unreadable_corpus(corpus_root):
    (corpus_root / "corpus/courts/court/court.yml").write_bytes(b"\xff")
    with pytest.raises(AgentValidationError, match="could not be read"):
        asyncio.run(
            get_file_based_corpus("court", "topic", resource_root=corpus_root)
        )
