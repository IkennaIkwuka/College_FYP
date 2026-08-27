from django.core.exceptions import PermissionDenied

from .models import AuditLog
from .services import log_action


class AccessDeniedLoggingMiddleware:
    """Logs FR-LOG-03 access-denial events for every `raise PermissionDenied(...)`
    project-wide (the 7 role decorators in accounts/decorators.py, the
    unassigned-role branch in accounts/views.py's dashboard, and
    results/views.py's course_results_entry) without editing any of them - Django
    wires up process_exception on a plain new-style middleware the same as an
    old-style one, no MiddlewareMixin needed.

    login_required (used inside every *_required decorator) redirects an anonymous
    visitor to the login page rather than raising PermissionDenied, so this only
    ever fires for an authenticated user hitting a route their role doesn't permit
    - matching FR-LOG-03's own wording ("the user, route, and reason"; a fully
    anonymous hit has no "user" to name).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not isinstance(exception, PermissionDenied):
            return None

        user = getattr(request, "user", None)
        actor = user if user is not None and user.is_authenticated else None

        log_action(
            action=AuditLog.ACCESS_DENIED,
            actor=actor,
            actor_username=actor.username if actor is not None else "",
            reason=str(exception),
            request=request,
        )
        # Returning None preserves Django's existing default-403 fallback - no
        # custom 403.html exists in this project, and this middleware must not
        # change that, only add a logging side effect.
        return None
