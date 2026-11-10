from allauth.account.adapter import DefaultAccountAdapter

from litigant_portal.app.client_ip import get_client_ip


class AccountAdapter(DefaultAccountAdapter):
    def get_client_ip(self, request):
        # allauth's rate limits count by this address.
        return get_client_ip(request)
