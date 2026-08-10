"""
Management command to clean up old anonymous identities and their associated data.

Identities with chat activity inside the audit retention window
(settings.AUDIT_RETENTION_DAYS) are never deleted, even with a smaller
--days, so AI conversation transcripts stay reviewable for that long.

Usage:
    python manage.py cleanup_sessions             # Dry run (default)
    python manage.py cleanup_sessions --delete    # Actually delete
    python manage.py cleanup_sessions --days=60   # Delete identities older than 60 days
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from litigant_portal.app.models import UserIdentity


class Command(BaseCommand):
    help = (
        "Clean up anonymous user identities (and their chat threads and "
        "uploads) outside the audit retention window"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Delete identities older than this many days "
                "(default: settings.AUDIT_RETENTION_DAYS). Never shrinks "
                "the audit guard on chat activity below that setting."
            ),
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete identities (default is dry run)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            days = settings.AUDIT_RETENTION_DAYS
        delete = options["delete"]
        now = timezone.now()
        cutoff = now - timedelta(days=days)
        guard_days = max(days, settings.AUDIT_RETENTION_DAYS)
        guard_cutoff = now - timedelta(days=guard_days)
        if guard_days > days:
            self.stdout.write(
                f"--days={days} is below AUDIT_RETENTION_DAYS="
                f"{settings.AUDIT_RETENTION_DAYS}; identities with chat "
                f"activity in the last {guard_days} days are kept."
            )

        old_identities = UserIdentity.objects.filter(
            user__isnull=True,
            created_at__lt=cutoff,
        ).exclude(chat_threads__messages__created_at__gte=guard_cutoff)

        count = old_identities.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No anonymous identities outside the {days}-day "
                    f"retention window."
                )
            )
            return

        if delete:
            deleted, details = old_identities.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted} objects: {details}")
            )
        else:
            thread_count = sum(i.chat_threads.count() for i in old_identities)
            upload_count = sum(i.uploads.count() for i in old_identities)
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {count} anonymous identities "
                    f"({thread_count} chat threads, {upload_count} uploads) "
                    f"outside the {days}-day retention window.\n"
                    f"Run with --delete to actually remove them."
                )
            )
