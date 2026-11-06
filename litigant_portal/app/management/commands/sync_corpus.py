import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from litigant_portal.app.features import features
from litigant_portal.app.selectors.corpus import corpus_load_courts
from litigant_portal.app.selectors.topic_flow import topic_court_find
from litigant_portal.app.services.corpus import corpus_sync

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync the database with the corpus (litigant_portal/corpus/)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--court",
            default=None,
            help="Court slug to deploy: its topics, flows, and site config. "
            "Defaults to the CORPUS_COURT setting. With neither set, a site "
            "with the court switcher keeps the court its topics are on. "
            "Otherwise, or with a blank --court, every court's topics, "
            "flows, contacts, and resources sync, and the site's court "
            "fields are left alone.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Also delete rows the corpus no longer names.",
        )

    def handle(self, *args, **options):
        court = options["court"]
        if court is None:
            court = settings.CORPUS_COURT
        if court is None and features().court_switcher:
            # Keep a court switched to on dev or QA through a restart or a
            # deploy that keeps the database (#886).
            court = topic_court_find()
            if court is not None and court not in corpus_load_courts():
                # A deploy renamed or removed the switched court's folder.
                # Syncing every court keeps the pod starting; an explicit
                # --court or CORPUS_COURT still fails on an unknown court.
                logger.warning(
                    "switched court %r is no longer in the corpus; "
                    "syncing every court",
                    court,
                )
                court = None
        try:
            summary = corpus_sync(
                court=court or None, strict=options["strict"]
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "Synced {variables} variables, {forms} forms, "
                "{topics} topics, {flows} flows; "
                "deleted {deleted} stale rows; "
                "{orphaned} orphan variables flagged.".format(**summary)
            )
        )
