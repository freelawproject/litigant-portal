from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from litigant_portal.app.client_ip import get_client_ip
from litigant_portal.app.services.user import (
    user_identity_anonymous_rekey,
    user_identity_anonymous_settle,
)
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY


class AccountAdapter(DefaultAccountAdapter):
    def get_client_ip(self, request):
        # allauth's rate limits count by this address.
        return get_client_ip(request)

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
        # The flush drops the session; unchosen work follows into the new one.
        session_key = request.session.get(ANONYMOUS_SESSION_KEY)
        super().logout(request)
        if not session_key:
            return
        request.session.create()
        request.session[ANONYMOUS_SESSION_KEY] = request.session.session_key
        user_identity_anonymous_rekey(
            session_key=session_key,
            new_session_key=request.session.session_key,
        )
