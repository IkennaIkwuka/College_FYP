from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from students.models import LEVEL_CHOICES, Department, StudentProfile

from .models import ADMIN_GROUP, BURSAR_GROUP, DEAN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, User

STAFF_GROUPS = [ADMIN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, BURSAR_GROUP, DEAN_GROUP]


class BootstrapFormMixin:
    """Adds Bootstrap's form-control/form-select classes to every field's widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, (forms.Select, forms.SelectMultiple)) else "form-control"
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
    """

    pass


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


class MatricLookupForm(BootstrapFormMixin, forms.Form):
    """Step 1 of self-registration - just normalizes the input. The actual
    AdmissionRecord lookup happens in the view, not here, since a not-found result
    needs to become a generic form error rather than a per-field validation error."""

    matric_number = forms.CharField(max_length=20, label="Matric Number")

    def clean_matric_number(self):
        return self.cleaned_data["matric_number"].strip().upper()


class PinForm(BootstrapFormMixin, forms.Form):
    pin = forms.CharField(max_length=6, label="PIN", widget=forms.PasswordInput(render_value=False))


class SelfRegisterPasswordForm(BootstrapFormMixin, forms.Form):
    """Step 3 of self-registration. Deliberately not SetPasswordForm/ChangePasswordForm -
    those bind to an already-saved User and call user.save() themselves, but at this
    point in the flow no User exists yet (it gets created in one shot, alongside the
    chosen password, once this form validates)."""

    password1 = forms.CharField(widget=forms.PasswordInput, label="New password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def __init__(self, *args, record, **kwargs):
        self.record = record
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords don't match.")
        elif password1:
            # No real User exists yet at this point, so build an unsaved stand-in from
            # the admission record's details purely so UserAttributeSimilarityValidator
            # has something to compare against - the same check an existing account's
            # password change already gets via ChangePasswordForm.
            dummy_user = User(
                username=self.record.matric_number.replace("/", ""),
                email=self.record.email,
                first_name=self.record.first_name,
                last_name=self.record.last_name,
            )
            try:
                validate_password(password1, user=dummy_user)
            except ValidationError as e:
                self.add_error("password1", e)
        return cleaned
