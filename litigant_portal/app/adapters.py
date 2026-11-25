import logging
import smtplib

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext as _

from litigant_portal.app.client_ip import get_client_ip
from litigant_portal.app.selectors.site import site_get
from litigant_portal.app.services.user import (
    user_identity_anonymous_settle,
    user_identity_merge_anonymous,
)
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def get_client_ip(self, request):
        # allauth's rate limits count by this address.
        return get_client_ip(request)

    def send_mail(self, template_prefix, email, context):
        # Mail renders without context processors.
        site = site_get()
        context = {
            "court_name": site.branding_name
            or site.court_name
            or "Litigant Portal",
            "link_days": settings.PASSWORD_RESET_TIMEOUT // (24 * 60 * 60),
            **context,
        }
        super().send_mail(template_prefix, email, context)

    def send_password_reset_mail(self, user, email, context):
        # An account an admin added has no password until the tester sets
        # one, so its reset link is the invite.
        if not user.has_usable_password():
            return self.send_mail("account/email/invite", email, context)
        return super().send_password_reset_mail(user, email, context)

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        try:
            super().send_confirmation_mail(request, emailconfirmation, signup)
        except (smtplib.SMTPException, OSError):
            logger.exception("Could not send a confirmation email")
            context.request.confirmation_send_failed = True

    def send_account_already_exists_mail(self, email):
        try:
            super().send_account_already_exists_mail(email)
        except (smtplib.SMTPException, OSError):
            logger.exception("Could not send an account exists email")
            context.request.confirmation_send_failed = True

    def respond_email_verification_sent(self, request, user):
        if not getattr(request, "confirmation_send_failed", False):
            return super().respond_email_verification_sent(request, user)
        # Drop allauth's "email sent" notice. The answer is the same for
        # a new address and a taken one.
        list(messages.get_messages(request))
        messages.error(
            request,
            _(
                "We could not send the email. Wait a few minutes, then "
                "sign in and we will send a new link."
            ),
        )
        return redirect("account_login")

    def post_login(self, request, user, **kwargs):
        """Send a login or signup that has anonymous work waiting to the
        answers page first, with where it was going as ``next``. Runs
        after ``next`` is resolved, which allauth's redirect hooks are
        not."""
        response = super().post_login(request, user, **kwargs)
        session_key = request.session.get(ANONYMOUS_SESSION_KEY)
        if not session_key:
            return response
        counts = user_identity_anonymous_settle(
            user=user, session_key=session_key
        )
        if not any(counts.values()):
            del request.session[ANONYMOUS_SESSION_KEY]
            return response
        query = urlencode({"next": response["Location"]})
        return redirect(f"{reverse('pages:anonymous_answers')}?{query}")

    def logout(self, request):
        # Unchosen work is kept, as on the page: the flush would leave it
        # to whoever uses this browser next.
        session_key = request.session.get(ANONYMOUS_SESSION_KEY)
        if session_key:
            user_identity_merge_anonymous(
                user=request.user, session_key=session_key
            )
        super().logout(request)
