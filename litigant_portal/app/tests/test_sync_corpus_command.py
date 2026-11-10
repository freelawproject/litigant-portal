"""The sync_corpus command resolves which court to sync, then hands it to
corpus_sync, which no longer reads CORPUS_COURT itself (#886).

With no court named and no CORPUS_COURT, a site with the court switcher
keeps the court its Topic rows are on, so a restart or a deploy that keeps
the database doesn't undo a switch."""

from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from litigant_portal.app.management.commands import sync_corpus

SUMMARY = dict.fromkeys(
    ("variables", "forms", "topics", "flows", "deleted", "orphaned"), 0
)


class SyncCorpusCourtTests(SimpleTestCase):
    def _court(self, *args, rows_on=None, with_topics=("alpha", "beta")):
        """The court the command syncs, with the Topic rows on
        ``rows_on`` (None: no one court) and the corpus giving topics to
        the courts in ``with_topics``."""

        def load_courts(*, with_topics_only=False):
            courts = ("alpha", "beta")
            if with_topics_only:
                courts = [c for c in courts if c in with_topics]
            return dict.fromkeys(courts)

        with (
            mock.patch.object(
                sync_corpus, "corpus_sync", return_value=SUMMARY
            ) as corpus_sync,
            mock.patch.object(
                sync_corpus, "topic_court_find", return_value=rows_on
            ),
            mock.patch.object(
                sync_corpus,
                "corpus_load_courts",
                side_effect=lambda with_topics=False: load_courts(
                    with_topics_only=with_topics
                ),
            ),
        ):
            call_command("sync_corpus", *args, stdout=mock.Mock())
        return corpus_sync.call_args.kwargs["court"]

    @override_settings(CORPUS_COURT="alpha")
    def test_no_court_falls_back_to_the_setting(self):
        self.assertEqual(self._court(rows_on="beta"), "alpha")

    @override_settings(CORPUS_COURT=None, DEPLOYMENT_ENV="qa")
    def test_no_court_and_no_setting_syncs_every_court(self):
        self.assertIsNone(self._court())

    @override_settings(CORPUS_COURT="alpha")
    def test_a_named_court_wins_over_the_setting(self):
        self.assertEqual(self._court("--court", "beta"), "beta")

    @override_settings(CORPUS_COURT="alpha", DEPLOYMENT_ENV="qa")
    def test_a_blank_court_syncs_every_court(self):
        self.assertIsNone(self._court("--court", "", rows_on="beta"))

    @override_settings(CORPUS_COURT=None, DEPLOYMENT_ENV="qa")
    def test_no_court_and_no_setting_keeps_the_switched_court(self):
        self.assertEqual(self._court(rows_on="beta"), "beta")

    @override_settings(CORPUS_COURT=None, DEPLOYMENT_ENV="prod", PILOT=True)
    def test_without_the_switcher_the_rows_are_not_read(self):
        self.assertIsNone(self._court(rows_on="beta"))

    @override_settings(CORPUS_COURT=None, DEPLOYMENT_ENV="qa")
    def test_a_switched_court_the_corpus_dropped_syncs_every_court(self):
        """A deploy that renames or removes the switched court's folder
        must not crash the pod at startup."""
        with self.assertLogs(sync_corpus.logger, level="WARNING"):
            self.assertIsNone(self._court(rows_on="gone"))

    @override_settings(CORPUS_COURT=None, DEPLOYMENT_ENV="qa")
    def test_a_switched_court_whose_topics_were_dropped_syncs_every_court(
        self,
    ):
        """A strict sync to a court with no topics deletes every Topic row,
        so startup must fall back the way the switcher refuses (#886)."""
        with self.assertLogs(sync_corpus.logger, level="WARNING"):
            self.assertIsNone(
                self._court(rows_on="beta", with_topics=("alpha",))
            )
