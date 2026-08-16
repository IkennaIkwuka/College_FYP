# Runs on every request. If a logged-in user still has must_change_password set
# (true for every account created via bulk import or the Add Student form), they get
# bounced away from wherever they were trying to go - the URLs listed below are the
# only ones they're allowed to visit instead, since blocking those would make it
# impossible to ever get off this flow.
from django.shortcuts import redirect
from django.urls import reverse

EXEMPT_URL_NAMES = {
    "accounts:change_password",
    "accounts:verify_pin",
    "accounts:send_pin_code",
    "accounts:logout",
}


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            exempt_paths = {reverse(name) for name in EXEMPT_URL_NAMES}
            if request.path not in exempt_paths and not request.path.startswith("/admin/"):
                # Students need to verify a PIN before they're allowed to set a new
                # password; staff (no student_profile) skip straight to that page,
                # same as before this flow existed. Once verified this session
                # (see accounts.views.verify_pin), they land on change_password too.
                student_profile = getattr(user, "student_profile", None)
                if student_profile is not None and not request.session.get("pin_verified"):
                    return redirect("accounts:verify_pin")
                return redirect("accounts:change_password")
        return self.get_response(request)
