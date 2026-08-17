from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy

from students.services import create_student_account, reset_student_pin, send_pin_email

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
    LoginForm,
    PinVerificationForm,
    StaffAccountForm,
    StaffEditForm,
    StudentAccountForm,
)
from .models import User
from .services import assign_staff_identity, force_password_reset


@admin_required
def register(request):
    if request.method == "POST":
        form = StudentAccountForm(request.POST)
        if form.is_valid():
            profile = create_student_account(
                matric_number=form.cleaned_data["matric_number"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                department=form.cleaned_data["department"],
                entry_level=form.cleaned_data["level"],
                admission_type=form.cleaned_data["admission_type"],
            )
            messages.success(
                request,
                f"Student {form.cleaned_data['matric_number']} added. "
                f'Their username is "{profile.user.username}"; '
                f'initial password is "{settings.DEFAULT_PASSWORD}". '
                "They'll request a verification code themselves at first login.",
            )
            return redirect("accounts:register")
    else:
        form = StudentAccountForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form, "default_password": settings.DEFAULT_PASSWORD},
    )


@login_required
def profile(request):
    # Students have their own richer profile page (academic details + editable
    # personal fields) - send anyone who lands here via a stale link or bookmark
    # to that instead of showing them this staff-oriented, view-only version.
    if request.user.is_student:
        return redirect("students:my_profile")
    return render(request, "accounts/profile.html")


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
            results.append({
                "label": staff_user.get_full_name() or staff_user.username,
                "sublabel": staff_user.email,
                "value": staff_user.username,
                "url": reverse("accounts:staff_edit", args=[staff_user.id]),
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
                staff_id=form.cleaned_data["staff_id"],
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
def staff_edit(request, pk):
    staff_user = get_object_or_404(User, pk=pk, groups__name__in=STAFF_GROUPS)

    if request.method == "POST":
        form = StaffEditForm(request.POST, instance=staff_user)
        if form.is_valid():
            form.save()
            staff_user.groups.remove(*Group.objects.filter(name__in=STAFF_GROUPS))
            staff_user.groups.add(form.cleaned_data["group"])
            messages.success(request, f"Updated {staff_user.get_full_name() or staff_user.username}.")
            return redirect("accounts:manage_staff")
    else:
        form = StaffEditForm(instance=staff_user)

    return render(
        request, "accounts/staff_form.html", {"form": form, "title": f"Edit {staff_user.username}"}
    )


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
    # Thin dispatcher - sends each user to their role's dashboard so 'dashboard'
    # (LOGIN_REDIRECT_URL) stays a stable target regardless of role count. is_admin
    # already covers is_superuser, checked first. Dean before HOD before lecturer/
    # registrar/bursar - a Dean or HOD is usually also a Lecturer and should land on
    # their more specific page; Registrar/Bursar are administrative-only roles that
    # don't overlap with the academic chain.
    if request.user.is_admin:
        return redirect("admin_dashboard")
    if request.user.is_dean:
        return redirect("dean_dashboard")
    if request.user.is_hod:
        return redirect("hod_dashboard")
    if request.user.is_registrar:
        return redirect("registrar_dashboard")
    if request.user.is_bursar:
        return redirect("bursar_dashboard")
    if request.user.is_lecturer:
        return redirect("lecturer_dashboard")
    if request.user.is_student:
        return redirect("student_dashboard")
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
