"""corpus_load_courts(with_topics=True): the courts the QA court switcher
offers (#886). A court with no topics yet (Portsmouth today) is left out:
a strict sync to it deletes every Topic row, so nothing would remember the
switch."""

from unittest import mock

from litigant_portal.app.selectors import corpus
from litigant_portal.app.selectors.corpus import corpus_load_courts


def test_with_topics_keeps_only_courts_that_have_topics():
    topics = {("north-dakota", "adult-name-change"): object()}
    with mock.patch.object(corpus, "corpus_load_topics", return_value=topics):
        courts = corpus_load_courts(with_topics=True)
    assert set(courts) == {"north-dakota"}


def test_without_the_flag_every_court_loads():
    with mock.patch.object(corpus, "corpus_load_topics", return_value={}):
        courts = corpus_load_courts()
    assert "north-dakota" in courts


def test_with_topics_uses_the_supplied_directory(tmp_path):
    for slug in ("alpha", "beta"):
        court = tmp_path / slug
        court.mkdir()
        (court / "court.yml").write_text(
            f"name: {slug}\ncourt_name: {slug} Court\n"
        )
    topic = tmp_path / "alpha" / "topics" / "pets"
    topic.mkdir(parents=True)
    (topic / "topic.yml").write_text("title: Pets\n")

    with mock.patch.object(corpus, "COURTS_DIR", tmp_path / "missing"):
        courts = corpus_load_courts(tmp_path, with_topics=True)

    assert set(courts) == {"alpha"}
