from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            raise PermissionDenied("This page is only available to admins.")
        return view_func(request, *args, **kwargs)

    return wrapper
