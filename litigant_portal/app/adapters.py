from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from litigant_portal.app.client_ip import get_client_ip
from litigant_portal.app.selectors.site import site_get
from litigant_portal.app.services.user import (
    user_identity_anonymous_settle,
    user_identity_merge_anonymous,
)
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY


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
