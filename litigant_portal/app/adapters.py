from allauth.account.adapter import DefaultAccountAdapter

from litigant_portal.app.client_ip import get_client_ip
from litigant_portal.app.services.user import user_identity_anonymous_rekey
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY


class AccountAdapter(DefaultAccountAdapter):
    def get_client_ip(self, request):
        # allauth's rate limits count by this address.
        return get_client_ip(request)

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
