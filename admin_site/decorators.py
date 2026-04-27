from functools import wraps

from django.contrib.auth.decorators import user_passes_test


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser


def superuser_required(view):
    """Allow only authenticated superusers; redirect to login otherwise."""

    @wraps(view)
    @user_passes_test(_is_superuser, login_url="/accounts/login/")
    def wrapped(request, *args, **kwargs):
        return view(request, *args, **kwargs)

    return wrapped
