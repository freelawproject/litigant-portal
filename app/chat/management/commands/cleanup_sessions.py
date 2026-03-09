"""
Management command to clean up old anonymous chat sessions.

Usage:
    python manage.py cleanup_sessions           # Dry run (default)
    python manage.py cleanup_sessions --delete  # Actually delete
    python manage.py cleanup_sessions --days=7  # Sessions older than 7 days
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import ChatSession


class Command(BaseCommand):
    help = "Clean up old anonymous chat sessions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete sessions older than this many days (default: 30)",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete sessions (default is dry run)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        delete = options["delete"]
        cutoff = timezone.now() - timedelta(days=days)

        # Find anonymous sessions (no user) older than cutoff
        old_sessions = ChatSession.objects.filter(
            user__isnull=True,
            updated_at__lt=cutoff,
        )

        count = old_sessions.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No anonymous sessions older than {days} days found."
                )
            )
            return

        if delete:
            # Delete cascades to messages
            deleted, details = old_sessions.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted} objects: {details}")
            )
        else:
            # Dry run - show what would be deleted
            message_count = sum(s.messages.count() for s in old_sessions)
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {count} anonymous sessions "
                    f"({message_count} messages) older than {days} days.\n"
                    f"Run with --delete to actually remove them."
                )
            )
