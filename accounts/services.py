import re
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

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
    """
    # Django's username field rejects "-", which staff IDs contain (e.g. "LU-RG-26-0001")
    # - LenientUsernameBackend (accounts/auth_backends.py) is what actually lets someone
    # log in typing the staff ID in its natural shape instead of this stripped form.
    user.username = re.sub(r"[^A-Za-z0-9]", "", user.staff_id).lower()
    user.set_password(settings.DEFAULT_PASSWORD)
    user.must_change_password = True
    return user


def force_password_reset(user):
    """Resets an existing account back to the same state a freshly-created one
    starts in: shared default password, forced change on next login. Covers both
    "forgot it" and "think it's compromised" - either way the old password stops
    working immediately.
    """
    user.set_password(settings.DEFAULT_PASSWORD)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])


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
