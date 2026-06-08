"""
Management command to clean up old anonymous identities and their associated data.

Usage:
    python manage.py cleanup_sessions           # Dry run (default)
    python manage.py cleanup_sessions --delete  # Actually delete
    python manage.py cleanup_sessions --days=7  # Identities older than 7 days
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from litigant_portal.app.models import UserIdentity


class Command(BaseCommand):
    help = "Clean up old anonymous user identities (and their chat/case data)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete identities older than this many days (default: 30)",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete identities (default is dry run)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        delete = options["delete"]
        cutoff = timezone.now() - timedelta(days=days)

        old_identities = UserIdentity.objects.filter(
            user__isnull=True,
            created_at__lt=cutoff,
        )

        count = old_identities.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No anonymous identities older than {days} days found."
                )
            )
            return

        if delete:
            deleted, details = old_identities.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted} objects: {details}")
            )
        else:
            chat_count = sum(i.chat_sessions.count() for i in old_identities)
            case_count = sum(i.case_infos.count() for i in old_identities)
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {count} anonymous identities "
                    f"({chat_count} chat sessions, {case_count} cases) "
                    f"older than {days} days.\n"
                    f"Run with --delete to actually remove them."
                )
            )
