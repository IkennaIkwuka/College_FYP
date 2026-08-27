from .models import AuditLog


def get_client_ip(request):
    """Best-effort client IP for the audit trail - checks X-Forwarded-For first
    (set by a reverse proxy, if one is ever put in front of this app; takes the
    left-most address, the original client) falling back to REMOTE_ADDR. This
    project has no documented reverse-proxy deployment yet, so the header check is
    forward-compatible groundwork, not a currently-exercised path - and it isn't
    hardened against a spoofed header on a direct connection, which is fine here
    (an audit trail, not an authorization decision).
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(*, action, actor=None, actor_username=None, target_description="", reason="", request=None):
    """Create one immutable AuditLog row. Explicit keyword args only, no ambient/
    thread-local state - nothing in this codebase uses thread-locals, contextvars,
    or a get_current_user() pattern, and this doesn't start.

    actor: a User instance, or None when no real account exists yet to point to
        (e.g. LOGIN_FAILED against an unknown username).
    actor_username: plain-text fallback. Defaults to actor.username when actor is
        given; pass it explicitly when actor is None but something was still typed
        (e.g. the raw username on a failed login).
    request: optional HttpRequest - when given, request_path and ip_address are
        filled in automatically. Leave unset from call sites with no request object
        (e.g. a service function that only got handed a User).
    """
    if actor_username is None:
        actor_username = actor.username if actor is not None else ""
    AuditLog.objects.create(
        actor=actor,
        actor_username=actor_username,
        action=action,
        target_description=target_description,
        reason=reason,
        request_path=request.path if request is not None else "",
        ip_address=get_client_ip(request) if request is not None else None,
    )
