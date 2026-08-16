from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from students.services import create_student_account

from .decorators import (
    admin_required,
    bursar_required,
    dean_required,
    hod_required,
    lecturer_required,
    registrar_required,
    student_required,
)
from .forms import STAFF_GROUPS, ChangePasswordForm, LoginForm, StaffAccountForm, StaffEditForm, StudentAccountForm
from .models import User
from .services import assign_staff_identity, force_password_reset


@admin_required
def register(request):
    if request.method == "POST":
        form = StudentAccountForm(request.POST)
        if form.is_valid():
            profile, raw_pin = create_student_account(
                matric_number=form.cleaned_data["matric_number"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                department=form.cleaned_data["department"],
                entry_level=form.cleaned_data["level"],
                admission_type=form.cleaned_data["admission_type"],
            )
            try:
                send_mail(
                    subject="Your LU-SIMS PIN",
                    message=(
                        f"Matric number: {profile.matric_number}\n"
                        f"PIN: {raw_pin}\n\n"
                        f'Log in with your username "{profile.user.username}" and the '
                        f'default password "{settings.DEFAULT_PASSWORD}", then enter this '
                        "PIN when prompted to set your own password."
                    ),
                    from_email=None,
                    recipient_list=[profile.user.email],
                )
            except Exception:
                messages.warning(
                    request,
                    f"Could not send the PIN email to {profile.user.email}. Follow up manually.",
                )
            messages.success(
                request,
                f"Student {form.cleaned_data['matric_number']} added. "
                f'Their username is "{profile.user.username}"; '
                f"initial password is \"{settings.DEFAULT_PASSWORD}\".",
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


@admin_required
def manage_staff(request):
    group_id = request.GET.get("group", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    staff_users = User.objects.filter(groups__name__in=STAFF_GROUPS).distinct().order_by("username")
    if group_id:
        staff_users = staff_users.filter(groups__id=group_id)
    if is_active:
        staff_users = staff_users.filter(is_active=(is_active == "1"))

    paginator = Paginator(staff_users, 10)
    staff_users = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    return render(
        request,
        "accounts/manage_staff.html",
        {
            "staff_users": staff_users,
            "querystring": querystring,
            "groups": Group.objects.filter(name__in=STAFF_GROUPS),
            "selected_group": group_id,
            "selected_is_active": is_active,
        },
    )


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
