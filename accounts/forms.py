from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from students.models import LEVEL_CHOICES, Department, StudentProfile

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

    For students specifically, a PIN field is added on top - the shared default
    password alone doesn't prove they own the email it was set up for, so a PIN
    emailed at account-creation time closes that gap before letting them replace it
    with something only they know. Staff accounts have no student_profile, so they
    get no PIN field at all - this form behaves exactly as it always has for them.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_profile = getattr(self.user, "student_profile", None)
        if self.student_profile is not None:
            self.fields["pin"] = forms.CharField(
                max_length=6, label="PIN", widget=forms.PasswordInput(render_value=False)
            )
            self.fields["pin"].widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        if self.student_profile is not None:
            # Lazily clear an expired lockout - no cron/Celery needed, the next attempt
            # after the cooldown passes just resets the counter right here.
            if self.student_profile.pin_locked_until is not None and not self.student_profile.is_pin_locked:
                self.student_profile.reset_pin_attempts()

            if self.student_profile.is_pin_locked:
                raise ValidationError("Too many wrong PIN attempts. Try again later.")

            pin = cleaned.get("pin")
            if pin and not self.student_profile.check_pin(pin):
                self.student_profile.register_failed_pin_attempt()
                if self.student_profile.is_pin_locked:
                    raise ValidationError("Too many wrong PIN attempts. Try again later.")
                self.add_error("pin", "Incorrect PIN.")
            elif pin:
                self.student_profile.reset_pin_attempts()
        return cleaned


class StudentAccountForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    matric_number = forms.CharField(max_length=20)
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    level = forms.ChoiceField(choices=LEVEL_CHOICES)

    def clean_matric_number(self):
        matric_number = self.cleaned_data["matric_number"].strip().upper()
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
    group = forms.ModelChoiceField(queryset=Group.objects.filter(name__in=STAFF_GROUPS), label="Role")

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
