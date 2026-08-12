from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from students.models import AdmissionRecord
from students.services import create_student_account

from .decorators import admin_required
from .forms import ChangePasswordForm, LoginForm, MatricLookupForm, PinForm, SelfRegisterPasswordForm, StudentAccountForm


@admin_required
def register(request):
    if request.method == "POST":
        form = StudentAccountForm(request.POST)
        if form.is_valid():
            create_student_account(
                matric_number=form.cleaned_data["matric_number"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                department=form.cleaned_data["department"],
                entry_level=form.cleaned_data["level"],
            )
            messages.success(
                request,
                f"Student {form.cleaned_data['matric_number']} added. "
                f"Their initial password is \"{settings.DEFAULT_PASSWORD}\".",
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
def dashboard(request):
    return render(request, "accounts/dashboard.html")


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


# Self-registration is a 3-step flow for students who don't have an account yet - see
# students.models.AdmissionRecord. State travels between steps via this one session key
# rather than URL params, so the record id/verification status can't be tampered with by
# just editing the URL.
SELF_REG_SESSION_KEY = "self_registration"


def self_register_matric(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = MatricLookupForm(request.POST)
        if form.is_valid():
            matric_number = form.cleaned_data["matric_number"]
            record = AdmissionRecord.objects.filter(matric_number=matric_number).first()
            if record is None:
                # Deliberately generic - AdmissionRecord rows are deleted on successful
                # registration (see self_register_password), so "never existed" and
                # "already used" are indistinguishable here by design, closing off
                # enumeration of which matric numbers have already registered.
                form.add_error(
                    "matric_number",
                    "We couldn't find an admission record for that matric number. "
                    "Contact IT Admin if you believe this is a mistake.",
                )
            elif record.is_locked:
                form.add_error(
                    "matric_number",
                    "Too many wrong PIN attempts for this matric number. Try again later.",
                )
            else:
                request.session[SELF_REG_SESSION_KEY] = {
                    "admission_record_id": record.id,
                    "pin_verified": False,
                }
                return redirect("accounts:self_register_pin")
    else:
        form = MatricLookupForm()

    return render(request, "accounts/self_register_matric.html", {"form": form})


def _get_self_reg_record(request):
    """Shared session-state guard for steps 2/3 - returns the AdmissionRecord, or None
    if the session doesn't have valid state (a skipped step, an expired session, or the
    record having vanished from under them, e.g. IT Admin deleted it)."""
    state = request.session.get(SELF_REG_SESSION_KEY)
    if not state:
        return None
    return AdmissionRecord.objects.filter(id=state["admission_record_id"]).first()


def self_register_pin(request):
    record = _get_self_reg_record(request)
    if record is None:
        return redirect("accounts:self_register_start")

    # Lazily clear an expired lockout - no cron/Celery needed, the next page load after
    # the cooldown passes just resets the counter right here.
    if record.locked_until is not None and not record.is_locked:
        record.reset_pin_attempts()

    if record.is_locked:
        messages.error(request, "Too many wrong PIN attempts. Try again later.")
        return redirect("accounts:self_register_start")

    if request.method == "POST":
        form = PinForm(request.POST)
        if form.is_valid():
            if record.check_pin(form.cleaned_data["pin"]):
                record.reset_pin_attempts()
                state = request.session[SELF_REG_SESSION_KEY]
                state["pin_verified"] = True
                request.session[SELF_REG_SESSION_KEY] = state
                return redirect("accounts:self_register_password")

            record.register_failed_pin_attempt()
            if record.is_locked:
                messages.error(request, "Too many wrong PIN attempts. Try again later.")
                return redirect("accounts:self_register_start")
            remaining = max(settings.PIN_MAX_ATTEMPTS - record.failed_attempts, 0)
            form.add_error("pin", f"Incorrect PIN. {remaining} attempt(s) remaining.")
    else:
        form = PinForm()

    return render(request, "accounts/self_register_pin.html", {"form": form})


def self_register_password(request):
    record = _get_self_reg_record(request)
    state = request.session.get(SELF_REG_SESSION_KEY)
    if record is None or not state or not state.get("pin_verified"):
        return redirect("accounts:self_register_start")

    if request.method == "POST":
        form = SelfRegisterPasswordForm(request.POST, record=record)
        if form.is_valid():
            try:
                with transaction.atomic():
                    profile = create_student_account(
                        matric_number=record.matric_number,
                        first_name=record.first_name,
                        last_name=record.last_name,
                        email=record.email,
                        department=record.department,
                        entry_level=record.entry_level,
                        password=form.cleaned_data["password1"],
                        must_change_password=False,
                    )
                    record.delete()
            except IntegrityError:
                # Two people finishing this record's registration at once - the loser's
                # create_student_account() hits StudentProfile's unique matric_number
                # constraint, rolling back the whole atomic block (including the delete).
                del request.session[SELF_REG_SESSION_KEY]
                messages.error(
                    request,
                    "This matric number was already registered - try logging in instead.",
                )
                return redirect("login")

            del request.session[SELF_REG_SESSION_KEY]
            messages.success(
                request,
                f'Registration complete. Your username is "{profile.user.username}" - '
                "use it with the password you just set to log in.",
            )
            return redirect("login")
    else:
        form = SelfRegisterPasswordForm(record=record)

    return render(request, "accounts/self_register_password.html", {"form": form})
