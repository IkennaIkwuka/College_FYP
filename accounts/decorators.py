from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """Stack on top of a view to require login AND admin role.

    @login_required alone only checks that someone is logged in; this adds the
    role check on top of it, so a logged-in Student hitting an admin-only URL
    gets a 403 instead of the page.
    """

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            raise PermissionDenied("This page is only available to admins.")
        return view_func(request, *args, **kwargs)

    return wrapper


def student_required(view_func):
    """Stack on top of a view to require login AND student role."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_student:
            raise PermissionDenied("This page is only available to students.")
        return view_func(request, *args, **kwargs)

    return wrapper


def hod_required(view_func):
    """Stack on top of a view to require login AND HOD role."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_hod:
            raise PermissionDenied("This page is only available to HODs.")
        return view_func(request, *args, **kwargs)

    return wrapper


def lecturer_required(view_func):
    """Stack on top of a view to require login AND lecturer role."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_lecturer:
            raise PermissionDenied("This page is only available to lecturers.")
        return view_func(request, *args, **kwargs)

    return wrapper


def registrar_required(view_func):
    """Stack on top of a view to require login AND registrar role."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_registrar:
            raise PermissionDenied("This page is only available to registrars.")
        return view_func(request, *args, **kwargs)

    return wrapper


def bursar_required(view_func):
    """Stack on top of a view to require login AND bursar role."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_bursar:
            raise PermissionDenied("This page is only available to bursars.")
        return view_func(request, *args, **kwargs)

    return wrapper


def dean_required(view_func):
    """Stack on top of a view to require login AND dean role."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_dean:
            raise PermissionDenied("This page is only available to deans.")
        return view_func(request, *args, **kwargs)

    return wrapper
