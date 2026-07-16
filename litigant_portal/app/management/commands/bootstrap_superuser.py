import os

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create or promote a superuser from SUPERUSER_EMAIL / SUPERUSER_PASSWORD"

    def handle(self, *args, **options):
        email = os.environ.get("SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("SUPERUSER_PASSWORD", "")

        if not email or not password:
            self.stdout.write(
                "SUPERUSER_EMAIL / SUPERUSER_PASSWORD not set; skipping "
                "superuser bootstrap."
            )
            return

        User = get_user_model()

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()

            if user is None:
                user = User.objects.create_superuser(
                    username=email,
                    email=email,
                    password=password,
                )
                EmailAddress.objects.get_or_create(
                    user=user,
                    email=user.email,
                    defaults={"verified": True, "primary": True},
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created superuser {email}.")
                )
            elif user.is_superuser:
                self.stdout.write(
                    f"Superuser {email} already exists; nothing to do."
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"User {email} already exists but is not a "
                        "superuser; refusing to promote a pre-existing "
                        "account. Remove or rename that account, or "
                        "promote it manually."
                    )
                )
