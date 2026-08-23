import re
import secrets

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import STAFF_ROLE_CODES, StaffIDSequence


def generate_staff_id(group):
    """Atomically reserve and return the next staff ID for a role, e.g. "LU-RG-26-0001".

    Scoped per role+year: the 4-digit sequence resets to 0001 each new appointment year,
    independently for each role.
    """
    role_code = STAFF_ROLE_CODES[group.name]
    year = timezone.now().year
    with transaction.atomic():
        seq, _ = StaffIDSequence.objects.select_for_update().get_or_create(
            role_code=role_code, year=year
        )
        seq.last_number += 1
        seq.save(update_fields=["last_number"])
    return f"{settings.UNIVERSITY_ABBREVIATION}-{role_code}-{year % 100:02d}-{seq.last_number:04d}"


def assign_staff_identity(user):
    """Mutates an unsaved User in place: username, and initial password/flag.

    Assumes the caller has already set user.staff_id (via generate_staff_id) - this just
    derives the username from it. Kept separate from admin.py so it's testable directly
    without driving the admin add_view. Caller is still responsible for user.save().

    No usable password is set here at all - there's no shared secret to leak. The
    account can't be logged into until an admin sends a setup link from the staff
    list (see send_staff_setup_link below), which is the only way in.
    """
    # Django's username field rejects "-", which staff IDs contain (e.g. "LU-RG-26-0001")
    # - LenientUsernameBackend (accounts/auth_backends.py) is what actually lets someone
    # log in typing the staff ID in its natural shape instead of this stripped form.
    user.username = re.sub(r"[^A-Za-z0-9]", "", user.staff_id).lower()
    user.set_unusable_password()
    user.must_change_password = True
    return user


def send_staff_setup_link(user, request):
    """Invalidates whatever password the account currently has (none, on a fresh
    account; a real one, if this is a resend) and emails a signed, expiring link
    that lets the owner set a real password directly - no PIN, no typed code.
    Owning the registered inbox is the entire identity proof here, unlike the
    student first-login flow (username-only login + emailed PIN typed into a
    form, see students.services.reset_student_first_login) - staff never attempt
    a login at all until after this link has been used.

    Reuses accounts:forgot_password_confirm as the landing page (ForgotPasswordConfirmView
    already clears must_change_password on success, which staff need too) rather
    than going through ForgotPasswordView/PasswordResetForm - that form's
    get_users() filters out any account without a usable password, which would
    silently exclude every staff account this is meant to invite. So the token/uid
    generation below is done directly instead, mirroring what PasswordResetForm.save()
    does internally (django.contrib.auth.forms).

    Safe to call repeatedly ("resend"): set_unusable_password() produces a fresh
    random hash each time, and since default_token_generator's HMAC includes
    user.password, that alone invalidates any previously issued link.
    """
    user.set_unusable_password()
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])

    current_site = get_current_site(request)
    context = {
        "user": user,
        "domain": current_site.domain,
        "site_name": current_site.name,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
        "protocol": "https" if request.is_secure() else "http",
    }
    subject = "".join(render_to_string("accounts/staff_setup_subject.txt", context).splitlines())
    message = render_to_string("accounts/staff_setup_email.txt", context)
    send_mail(subject=subject, message=message, from_email=None, recipient_list=[user.email])


def generate_code(digits=6):
    """Cryptographically-random numeric code, zero-padded, e.g. '004821'.

    Same body as students.services.generate_pin - can't import it (accounts can't
    depend on students, see accounts.models.User's email-change fields docstring).
    """
    return f"{secrets.randbelow(10 ** digits):0{digits}d}"


def send_email_change_code(user, raw_code):
    send_mail(
        subject="Confirm your new LU-SIMS email",
        message=(
            f"Code: {raw_code}\n\n"
            "Enter this code to confirm this is your new LU-SIMS login email. "
            "If you didn't request this, you can ignore this message - your "
            "email won't change."
        ),
        from_email=None,
        recipient_list=[user.pending_email],
    )


def send_email_change_notice(user, old_email):
    send_mail(
        subject="Your LU-SIMS login email was changed",
        message=(
            f"Your LU-SIMS account's login email was changed to {user.email}.\n\n"
            "If this wasn't you, contact IT Admin or the Registrar's office "
            "immediately."
        ),
        from_email=None,
        recipient_list=[old_email],
    )
