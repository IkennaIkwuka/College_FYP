from accounts import views as accounts_views
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from students import views as students_views
from students.services import reset_student_pin, send_pin_email


# Thin role dispatchers for the shared, role-neutral /profile/ and /profile/edit/
# URLs (mirrors ec4631b's /login/ and /dashboard/ move - the URL itself shouldn't
# reveal what kind of account you're looking at). Live here rather than in
# accounts.views because students depends on accounts, never the reverse -
# accounts can't import students.views itself, but the project's own URL
# composition layer is free to depend on both.


@login_required
def profile(request):
    if request.user.is_student:
        return students_views.my_profile(request)
    return accounts_views.profile(request)


@login_required
def profile_edit(request):
    if request.user.is_student:
        return students_views.my_profile_edit(request)
    return accounts_views.profile_edit(request)


# Same reasoning as above, one level down: this view's own logic is entirely
# accounts' (gates on must_change_password, redirects into the accounts verify-pin
# flow) but its one action - reissue a student's PIN - needs students.services,
# which accounts can't import directly. Registered under accounts/urls.py so the
# URL name stays accounts:send_pin_code, matching every other reference to it
# (middleware, templates, tests) - only the function's home module changes.
@login_required
def send_pin_code(request):
    if not request.user.must_change_password:
        return redirect("dashboard")
    student_profile = getattr(request.user, "student_profile", None)
    if student_profile is None:
        return redirect("accounts:change_password")

    if request.method == "POST":
        raw_pin = reset_student_pin(student_profile)
        try:
            send_pin_email(student_profile, raw_pin)
            messages.success(request, f"Code sent to {request.user.email}.")
        except Exception:
            messages.warning(
                request, f"Could not send the code to {request.user.email}. Try again shortly."
            )
    return redirect("accounts:verify_pin")
