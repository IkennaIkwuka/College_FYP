# Runs on every request. If a logged-in user still has must_change_password set
# (true for every account created via bulk import or the Add Student form), they get
# bounced to the change-password page no matter what URL they were actually trying to
# reach - the two pages listed below are the only ones they're allowed to visit instead,
# since blocking those would make it impossible to ever get off this page.
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
