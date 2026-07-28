import os

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from litigant_portal.app.services.user import DEVELOPERS_GROUP


class Command(BaseCommand):
    help = "Create a Developers-group user from DEV_USER_EMAIL / DEV_USER_PASSWORD"

    def handle(self, *args, **options):
        email = os.environ.get("DEV_USER_EMAIL", "").strip()
        password = os.environ.get("DEV_USER_PASSWORD", "")

        if not email or not password:
            self.stdout.write(
                "DEV_USER_EMAIL / DEV_USER_PASSWORD not set; skipping "
                "dev user bootstrap."
            )
            return

        User = get_user_model()

        with transaction.atomic():
            # get_or_create so the command works standalone; the
            # post-migrate signal attaches the group's permissions.
            group, _ = Group.objects.get_or_create(name=DEVELOPERS_GROUP)
            user = User.objects.filter(email__iexact=email).first()

            if user is None:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                )
                user.groups.add(group)
                EmailAddress.objects.get_or_create(
                    user=user,
                    email=user.email,
                    defaults={"verified": True, "primary": True},
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created dev user {email}.")
                )
            elif user.groups.filter(pk=group.pk).exists():
                self.stdout.write(
                    f"Dev user {email} already exists; nothing to do."
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"User {email} already exists but is not a "
                        "developer; refusing to promote a pre-existing "
                        "account. Remove or rename that account, or "
                        "promote it manually."
                    )
                )
