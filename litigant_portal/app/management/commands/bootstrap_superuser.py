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
                self.stdout.write(
                    self.style.SUCCESS(f"Created superuser {email}.")
                )
            elif user.is_staff and user.is_superuser:
                self.stdout.write(
                    f"Superuser {email} already exists; nothing to do."
                )
            else:
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["is_staff", "is_superuser"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Promoted existing user {email} to superuser."
                    )
                )

            EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"verified": True, "primary": True},
            )
