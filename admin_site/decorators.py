from functools import wraps

from django.contrib.auth.decorators import user_passes_test


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def admin_required(view):
    """Allow staff or superusers; redirect to login otherwise."""

    @wraps(view)
    @user_passes_test(_is_admin, login_url="/accounts/login/")
    def wrapped(request, *args, **kwargs):
        return view(request, *args, **kwargs)

    return wrapped
