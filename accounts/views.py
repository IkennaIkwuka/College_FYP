from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from .decorators import (
    admin_required,
    bursar_required,
    dean_required,
    hod_required,
    lecturer_required,
    registrar_required,
    student_required,
)
from .forms import (
    STAFF_GROUPS,
    ChangePasswordForm,
    EmailChangeCodeForm,
    ForgotPasswordForm,
    LoginForm,
    PinVerificationForm,
    PreferredUsernameForm,
    RequestEmailChangeForm,
    SelfChangePasswordForm,
    StaffAccountForm,
    StaffEditForm,
    StaffProfileForm,
)
from .models import User
from .services import (
    assign_staff_identity,
    force_password_reset,
    generate_code,
    generate_staff_id,
    send_email_change_code,
    send_email_change_notice,
)


@login_required
def profile(request):
    # Reached only for non-student accounts - lu_sims.views.profile (the shared,
    # role-neutral /profile/ dispatcher) routes students to students.views.my_profile
    # instead, since accounts can't import students.
    return render(request, "accounts/profile.html")


@login_required
def profile_edit(request):
    # Two forms on one page (mirrors students.views.my_profile_edit's pattern) - the
    # submit button's name says which one was actually submitted.
    if request.method == "POST" and "save_profile" in request.POST:
        profile_form = StaffProfileForm(request.POST, instance=request.user)
        username_form = PreferredUsernameForm(user=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    elif request.method == "POST":
        username_form = PreferredUsernameForm(request.POST, user=request.user)
        profile_form = StaffProfileForm(instance=request.user)
        if username_form.is_valid():
            request.user.preferred_username = username_form.cleaned_data["preferred_username"]
            request.user.preferred_username_changed_at = timezone.now()
            request.user.save(update_fields=["preferred_username", "preferred_username_changed_at"])
            messages.success(request, "Preferred username updated.")
            return redirect("profile")
    else:
        profile_form = StaffProfileForm(instance=request.user)
        username_form = PreferredUsernameForm(user=request.user)

    return render(request, "accounts/profile_edit.html", {"form": username_form, "profile_form": profile_form})


@login_required
def request_email_change(request):
    if request.method == "POST":
        form = RequestEmailChangeForm(request.POST, user=request.user)
        if form.is_valid():
            new_email = form.cleaned_data["new_email"]
            request.user.pending_email = new_email

            # Enumeration-oracle fix: the requester sees the same "code sent" message
            # and lands on the same confirm page whether new_email is free or already
            # taken by someone else - only a genuinely free email actually gets a code,
            # so there's nothing for a guesser to observe either way.
            email_taken = User.objects.exclude(pk=request.user.pk).filter(email__iexact=new_email).exists()
            if email_taken:
                request.user.email_change_code_hash = ""
                request.user.save(update_fields=["pending_email", "email_change_code_hash"])
            else:
                raw_code = generate_code()
                request.user.email_change_code_hash = make_password(raw_code)
                request.user.save(update_fields=["pending_email", "email_change_code_hash"])
                try:
                    send_email_change_code(request.user, raw_code)
                except Exception:
                    messages.warning(
                        request, f"Could not send the code to {request.user.pending_email}. Try again shortly."
                    )
                    return redirect("accounts:confirm_email_change")

            messages.success(request, f"Code sent to {request.user.pending_email}.")
            return redirect("accounts:confirm_email_change")
    else:
        form = RequestEmailChangeForm(user=request.user)

    return render(request, "accounts/request_email_change.html", {"form": form})


@login_required
def confirm_email_change(request):
    if not request.user.pending_email:
        return redirect("accounts:request_email_change")

    if request.method == "POST":
        form = EmailChangeCodeForm(request.POST, user=request.user)
        if form.is_valid():
            old_email = request.user.email
            request.user.email = request.user.pending_email
            request.user.pending_email = ""
            request.user.email_change_code_hash = ""
            request.user.email_changed_at = timezone.now()
            request.user.save(update_fields=["email", "pending_email", "email_change_code_hash", "email_changed_at"])
            try:
                send_email_change_notice(request.user, old_email)
            except Exception:
                pass  # best-effort - the actual change already succeeded
            messages.success(request, "Email updated.")
            return redirect("profile")
    else:
        form = EmailChangeCodeForm(user=request.user)

    return render(request, "accounts/confirm_email_change.html", {"form": form})


@login_required
def resend_email_change_code(request):
    if not request.user.pending_email:
        return redirect("accounts:request_email_change")

    if request.method == "POST":
        raw_code = generate_code()
        request.user.email_change_code_hash = make_password(raw_code)
        request.user.save(update_fields=["email_change_code_hash"])
        try:
            send_email_change_code(request.user, raw_code)
            messages.success(request, f"Code sent to {request.user.pending_email}.")
        except Exception:
            messages.warning(
                request, f"Could not send the code to {request.user.pending_email}. Try again shortly."
            )
    return redirect("accounts:confirm_email_change")


def _filtered_staff_users(request):
    query = request.GET.get("q", "").strip()
    group_id = request.GET.get("group", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    staff_users = User.objects.filter(groups__name__in=STAFF_GROUPS).distinct().order_by("username")
    if query:
        staff_users = staff_users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(staff_id__icontains=query)
        )
    if group_id:
        staff_users = staff_users.filter(groups__id=group_id)
    if is_active:
        staff_users = staff_users.filter(is_active=(is_active == "1"))
    return staff_users, query, group_id, is_active


@admin_required
def manage_staff(request):
    staff_users, query, group_id, is_active = _filtered_staff_users(request)

    paginator = Paginator(staff_users, 10)
    staff_users = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    return render(
        request,
        "accounts/manage_staff.html",
        {
            "query": query,
            "staff_users": staff_users,
            "querystring": querystring,
            "groups": Group.objects.filter(name__in=STAFF_GROUPS),
            "selected_group": group_id,
            "selected_is_active": is_active,
        },
    )


@admin_required
def staff_search_suggestions(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        staff_users, *_ = _filtered_staff_users(request)
        for staff_user in staff_users[:8]:
            role = staff_user.groups.first()
            results.append({
                "label": staff_user.get_full_name() or staff_user.username,
                "sublabel": role.name if role else "",
                "value": staff_user.username,
                "url": reverse("accounts:staff_detail", args=[staff_user.id]),
            })
    return JsonResponse({"results": results})


@admin_required
def staff_add(request):
    if request.method == "POST":
        form = StaffAccountForm(request.POST)
        if form.is_valid():
            user = User(
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                staff_id=generate_staff_id(form.cleaned_data["group"]),
            )
            assign_staff_identity(user)
            user.save()
            user.groups.add(form.cleaned_data["group"])
            messages.success(
                request,
                f'Staff account created. Username is "{user.username}"; '
                f'initial password is "{settings.DEFAULT_PASSWORD}".',
            )
            return redirect("accounts:manage_staff")
    else:
        form = StaffAccountForm()

    return render(
        request,
        "accounts/staff_form.html",
        {"form": form, "default_password": settings.DEFAULT_PASSWORD},
    )


@admin_required
def staff_detail(request, pk):
    staff_user = get_object_or_404(User, pk=pk, groups__name__in=STAFF_GROUPS)
    return render(request, "accounts/staff_detail.html", {"staff_user": staff_user})


@admin_required
def staff_edit(request, pk):
    staff_user = get_object_or_404(User, pk=pk, groups__name__in=STAFF_GROUPS)

    if request.method == "POST":
        form = StaffEditForm(request.POST, instance=staff_user)
        if form.is_valid():
            form.save()
            staff_user.groups.remove(*Group.objects.filter(name__in=STAFF_GROUPS))
            staff_user.groups.add(form.cleaned_data["group"])
            messages.success(request, f"Updated {staff_user.get_full_name() or staff_user.username}.")
            return redirect("accounts:staff_detail", pk=staff_user.id)
    else:
        form = StaffEditForm(instance=staff_user)

    return render(request, "accounts/staff_edit.html", {"form": form, "staff_user": staff_user})


@admin_required
def staff_force_password_reset(request, pk):
    staff_user = get_object_or_404(User, pk=pk, groups__name__in=STAFF_GROUPS)

    if request.method == "POST":
        force_password_reset(staff_user)
        messages.success(
            request,
            f"Password reset for {staff_user.get_full_name() or staff_user.username}. "
            f'They\'ll need to log in with the default password ("{settings.DEFAULT_PASSWORD}") '
            "and set a new one.",
        )
    return redirect("accounts:manage_staff")


@login_required
def dashboard(request):
    # Thin dispatcher - calls straight into each role's dashboard view so
    # 'dashboard' (LOGIN_REDIRECT_URL) stays a stable, role-neutral URL regardless
    # of role count. Calls the view function directly rather than redirect()ing to
    # it, same reasoning as lu_sims.views.profile: the address bar shouldn't reveal
    # what role landed here. is_admin already covers is_superuser, checked first.
    # Dean before HOD before lecturer/registrar/bursar - a Dean or HOD is usually
    # also a Lecturer and should land on their more specific page; Registrar/Bursar
    # are administrative-only roles that don't overlap with the academic chain.
    if request.user.is_admin:
        return admin_dashboard(request)
    if request.user.is_dean:
        return dean_dashboard(request)
    if request.user.is_hod:
        return hod_dashboard(request)
    if request.user.is_registrar:
        return registrar_dashboard(request)
    if request.user.is_bursar:
        return bursar_dashboard(request)
    if request.user.is_lecturer:
        return lecturer_dashboard(request)
    if request.user.is_student:
        return student_dashboard(request)
    raise PermissionDenied("Your account isn't assigned to a role yet. Contact IT Admin.")


@admin_required
def admin_dashboard(request):
    return render(request, "accounts/admin_dashboard.html")


@dean_required
def dean_dashboard(request):
    return render(request, "accounts/dean_dashboard.html")


@hod_required
def hod_dashboard(request):
    return render(request, "accounts/hod_dashboard.html")


@registrar_required
def registrar_dashboard(request):
    return render(request, "accounts/registrar_dashboard.html")


@bursar_required
def bursar_dashboard(request):
    return render(request, "accounts/bursar_dashboard.html")


@lecturer_required
def lecturer_dashboard(request):
    return render(request, "accounts/lecturer_dashboard.html")


@student_required
def student_dashboard(request):
    return render(request, "accounts/student_dashboard.html")


class PortalLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm

    def get_context_data(self, **kwargs):
        # LoginView doesn't know about DEFAULT_PASSWORD on its own - this just
        # hands it to the template so the "first time logging in?" tip stays in sync
        # with whatever the setting is currently bumped to, instead of being hardcoded.
        context = super().get_context_data(**kwargs)
        context["default_password"] = settings.DEFAULT_PASSWORD
        return context


class ForcedPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/change_password.html"
    form_class = ChangePasswordForm
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=["must_change_password"])
        messages.success(self.request, "Password changed.")
        return response


class SelfChangePasswordView(auth_views.PasswordChangeView):
    """Voluntary change for someone already in good standing (must_change_password
    is False, or the ForcePasswordChangeMiddleware would have already routed them
    to accounts:change_password instead - see accounts/middleware.py).
    """

    template_name = "accounts/self_change_password.html"
    form_class = SelfChangePasswordForm
    success_url = reverse_lazy("profile")

    def form_valid(self, form):
        # PasswordChangeView.form_valid() already calls update_session_auth_hash,
        # so the user stays logged in after this.
        response = super().form_valid(form)
        messages.success(self.request, "Password changed.")
        return response


class ForgotPasswordView(auth_views.PasswordResetView):
    template_name = "accounts/forgot_password.html"
    form_class = ForgotPasswordForm
    email_template_name = "accounts/forgot_password_email.txt"
    subject_template_name = "accounts/forgot_password_subject.txt"
    success_url = reverse_lazy("accounts:forgot_password_done")


class ForgotPasswordDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/forgot_password_done.html"


class ForgotPasswordConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/forgot_password_confirm.html"
    form_class = ChangePasswordForm
    success_url = reverse_lazy("accounts:forgot_password_complete")

    def form_valid(self, form):
        # A completed reset already proves the user owns the email on file and
        # gives them a real, self-chosen password - the same thing verify_pin +
        # change_password prove together during a forced first login. Don't route
        # them back through the PIN gate afterward.
        response = super().form_valid(form)
        form.user.must_change_password = False
        form.user.save(update_fields=["must_change_password"])
        return response


class ForgotPasswordCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/forgot_password_complete.html"


@login_required
def verify_pin(request):
    # Only students mid forced-first-login belong here at all - anyone else (already
    # changed their password, or a staff account with no PIN) gets sent past it.
    if not request.user.must_change_password:
        return redirect("dashboard")
    student_profile = getattr(request.user, "student_profile", None)
    if student_profile is None or request.session.get("pin_verified"):
        return redirect("accounts:change_password")

    if request.method == "POST":
        form = PinVerificationForm(request.POST, student_profile=student_profile)
        if form.is_valid():
            request.session["pin_verified"] = True
            return redirect("accounts:change_password")
    else:
        form = PinVerificationForm(student_profile=student_profile)

    return render(request, "accounts/verify_pin.html", {"form": form})


