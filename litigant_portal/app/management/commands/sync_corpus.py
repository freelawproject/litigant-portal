from django.core.management.base import BaseCommand, CommandError

from litigant_portal.app.services.corpus import corpus_sync


class Command(BaseCommand):
    help = "Sync the database with the corpus (litigant_portal/corpus/)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--court",
            default=None,
            help="Court slug to deploy: its topics, flows, and site config. "
            "Defaults to the CORPUS_COURT setting. With neither set, every "
            "court's topics, flows, contacts, and resources sync, and "
            "the site's court fields are left alone.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Also delete rows the corpus no longer names.",
        )

    def handle(self, *args, **options):
        try:
            summary = corpus_sync(
                court=options["court"], strict=options["strict"]
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
