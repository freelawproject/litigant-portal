import logging
import os

from allauth.account.models import EmailAddress
from allauth.account.views import LoginView
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


def ensure_dev_superuser():
    """Lazily create a dev superuser from DEV_EMAIL / DEV_PASSWORD env vars.

    No-op unless both env vars are set. Idempotent on repeated calls. Intended
    for local docker dev — production never sets these vars.
    """
    email = os.environ.get("DEV_EMAIL")
    password = os.environ.get("DEV_PASSWORD")
    if not (email and password):
        return

    User = get_user_model()
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create_superuser(
            username=email,
            email=email,
            password=password,
        )
        logger.info("Created dev superuser %s", email)

    EmailAddress.objects.get_or_create(
        user=user,
        email=email,
        defaults={"verified": True, "primary": True},
    )


class DevAwareLoginView(LoginView):
    def dispatch(self, request, *args, **kwargs):
        ensure_dev_superuser()
        return super().dispatch(request, *args, **kwargs)
