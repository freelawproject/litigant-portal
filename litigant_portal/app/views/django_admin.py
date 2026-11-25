from allauth.account.decorators import secure_admin_login
from allauth.account.utils import get_next_redirect_url
from django.shortcuts import redirect


@secure_admin_login
def _to_admin(request, extra_context=None):
    # Django's own login form would sign an account in with no code step.
    return redirect(get_next_redirect_url(request) or "admin:index")


def login(request, extra_context=None):
    # A signed-in account without admin access would get a bare 403.
    if request.user.is_authenticated and not request.user.is_staff:
        return redirect("pages:home")
    return _to_admin(request, extra_context)
