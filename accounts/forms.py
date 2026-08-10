from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from students.models import LEVEL_CHOICES, Department, StudentProfile

from .models import User


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


class ChangePasswordForm(BootstrapFormMixin, PasswordChangeForm):
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
