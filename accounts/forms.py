import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import Group
from django.db.models import Q

from .models import ADMIN_GROUP, BURSAR_GROUP, DEAN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, User

STAFF_GROUPS = [ADMIN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, BURSAR_GROUP, DEAN_GROUP]

# A real university has exactly one Registrar and one Bursar - these two groups are
# capped at one active member each, unlike every other staff group.
CAPPED_GROUPS = {REGISTRAR_GROUP, BURSAR_GROUP}


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


class PreferredUsernameForm(BootstrapFormMixin, forms.Form):
    """Lets a staff or student account set an optional second login credential.

    Takes the acting user as an explicit kwarg (like PinVerificationForm takes
    student_profile) rather than binding to a model instance - it only ever touches
    User.preferred_username, not the rest of the profile.
    """

    preferred_username = forms.CharField(max_length=150, required=False, label="Preferred username")

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_preferred_username(self):
        value = self.cleaned_data["preferred_username"].strip()
        if not value:
            return None  # clearing it back to system-only login
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{3,149}", value):
            raise forms.ValidationError(
                "Must start with a letter, 4-150 characters, letters/numbers/./_/- only."
            )
        value = value.lower()
        if User.objects.exclude(pk=self.user.pk).filter(
            Q(username__iexact=value) | Q(preferred_username__iexact=value)
        ).exists():
            raise forms.ValidationError("That username is already taken.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        locked_until = self.user.preferred_username_locked_until
        if locked_until and cleaned_data.get("preferred_username") != self.user.preferred_username:
            raise forms.ValidationError(
                f"You can change your preferred username again on {locked_until:%Y-%m-%d}."
            )
        return cleaned_data


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

    def clean_group(self):
        group = self.cleaned_data["group"]
        if group.name in CAPPED_GROUPS and User.objects.filter(groups=group, is_active=True).exists():
            raise forms.ValidationError(
                f"There is already an active {group.name}. Deactivate them first."
            )
        return group


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

    def clean(self):
        cleaned_data = super().clean()
        group = cleaned_data.get("group")
        is_active = cleaned_data.get("is_active", False)
        if group is None:
            return cleaned_data

        def other_active_members(group_name):
            return User.objects.filter(groups__name=group_name, is_active=True).exclude(pk=self.instance.pk)

        current_group = self.instance.groups.filter(name__in=STAFF_GROUPS).first()
        current_group_name = current_group.name if current_group else None

        # If this account is already one of several active members of a capped group -
        # a pre-existing violation, not something this edit is creating - block every
        # change to it except the one that resolves the violation (deactivating it
        # without also switching its role), rather than silently letting other fields
        # through while the violation persists.
        is_over_cap = (
            self.instance.is_active
            and current_group_name in CAPPED_GROUPS
            and other_active_members(current_group_name).exists()
        )
        if is_over_cap:
            is_resolving_edit = not is_active and group.name == current_group_name
            if not is_resolving_edit:
                raise forms.ValidationError(
                    f"This account is one of multiple active {current_group_name} accounts, which a "
                    "university should only have one of. Deactivate it to resolve this before making "
                    "any other change."
                )
            return cleaned_data

        if group.name in CAPPED_GROUPS and is_active and other_active_members(group.name).exists():
            raise forms.ValidationError(
                f"There is already an active {group.name}. Deactivate them first."
            )

        return cleaned_data
