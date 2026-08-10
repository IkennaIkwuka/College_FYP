from django.shortcuts import redirect
from django.urls import reverse

EXEMPT_URL_NAMES = {"accounts:change_password", "accounts:logout"}


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            exempt_paths = {reverse(name) for name in EXEMPT_URL_NAMES}
            if request.path not in exempt_paths and not request.path.startswith("/admin/"):
                return redirect("accounts:change_password")
        return self.get_response(request)
