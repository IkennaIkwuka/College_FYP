from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import Group
from lu_sims.id_format import InvalidAcademicID, format_academic_id
from students.models import ADMISSION_TYPE_CHOICES, LEVEL_CHOICES, Department, StudentProfile

from .models import ADMIN_GROUP, BURSAR_GROUP, DEAN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, User

STAFF_GROUPS = [ADMIN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, BURSAR_GROUP, DEAN_GROUP]


class BootstrapFormMixin:
    """Adds Bootstrap's form-control/form-select/form-check-input classes to every field's widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                # form-control stretches a checkbox into a full-width block instead of a
                # normal small checkbox - Bootstrap's own class for a bare checkbox input.
                css_class = "form-check-input"
            else:
                css_class = "form-control"
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class ChangePasswordForm(BootstrapFormMixin, SetPasswordForm):
    """Sets a new password without asking for the old one.

    SetPasswordForm is what Django normally uses for password-reset-by-email links,
    where the user proved who they are via the email token instead of a password -
    it fits here too, since a first-time login already proves who they are via the
    default password, and asking them to also type that default password back in
    as "confirm your old password" would just be an extra step for no real benefit.

    For students, proving they own the email on file happens earlier now - the
    verify-pin step (accounts:verify_pin) that the forced-password-change middleware
    routes them through first - so this form itself no longer needs to know anything
    about PINs or student_profile at all.
    """


class PinVerificationForm(BootstrapFormMixin, forms.Form):
    """First-login gate for students, ahead of ChangePasswordForm.

    Deliberately its own step rather than a field bolted onto the password form -
    the student may need to click "send code" (accounts:send_pin_code) before they
    have anything to type here at all, which doesn't fit inside a single submission.
    """

    pin = forms.CharField(
        max_length=6,
        label="Verification code",
        widget=forms.TextInput(attrs={"placeholder": "000000", "inputmode": "numeric", "autocomplete": "one-time-code"}),
    )

    def __init__(self, *args, student_profile, **kwargs):
        self.student_profile = student_profile
        super().__init__(*args, **kwargs)

    def clean_pin(self):
        pin = self.cleaned_data["pin"]
        profile = self.student_profile

        # Lazily clear an expired lockout - no cron/Celery needed, the next attempt
        # after the cooldown passes just resets the counter right here.
        if profile.pin_locked_until is not None and not profile.is_pin_locked:
            profile.reset_pin_attempts()

        if profile.is_pin_locked:
            raise forms.ValidationError("Too many wrong attempts. Try again later.")

        if not profile.pin_hash:
            raise forms.ValidationError('No code has been sent yet - click "Send code" first.')

        if not profile.check_pin(pin):
            profile.register_failed_pin_attempt()
            if profile.is_pin_locked:
                raise forms.ValidationError("Too many wrong attempts. Try again later.")
            raise forms.ValidationError("Incorrect code.")

        profile.reset_pin_attempts()
        return pin


class StudentAccountForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    matric_number = forms.CharField(max_length=20)
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    level = forms.ChoiceField(choices=LEVEL_CHOICES)
    admission_type = forms.ChoiceField(choices=ADMISSION_TYPE_CHOICES)

    def clean_matric_number(self):
        try:
            matric_number = format_academic_id(self.cleaned_data["matric_number"])
        except InvalidAcademicID as e:
            raise forms.ValidationError(str(e))
        if StudentProfile.objects.filter(matric_number=matric_number).exists():
            raise forms.ValidationError("A student with this matric number already exists.")
        return matric_number

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class StaffAccountForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    staff_id = forms.CharField(max_length=20)
    group = forms.ModelChoiceField(queryset=Group.objects.filter(name__in=STAFF_GROUPS), label="Role")

    def clean_staff_id(self):
        try:
            staff_id = format_academic_id(self.cleaned_data["staff_id"])
        except InvalidAcademicID as e:
            raise forms.ValidationError(str(e))
        if User.objects.filter(staff_id=staff_id).exists():
            raise forms.ValidationError("A staff member with this ID already exists.")
        return staff_id

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class StaffEditForm(BootstrapFormMixin, forms.ModelForm):
    # Separate from StaffAccountForm (create-only) rather than reused - a plain
    # clean_email() uniqueness check would wrongly flag the user's own unchanged email
    # as a duplicate. ModelForm handles "unique excluding this instance" for free.
    group = forms.ModelChoiceField(queryset=Group.objects.filter(name__in=STAFF_GROUPS), label="Role")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            current_group = self.instance.groups.filter(name__in=STAFF_GROUPS).first()
            if current_group:
                self.fields["group"].initial = current_group
