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
