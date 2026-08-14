import secrets

from accounts.models import STUDENT_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group

from .models import StudentProfile


def generate_pin(digits=6):
    """Cryptographically-random numeric PIN, zero-padded, e.g. '004821'."""
    return f"{secrets.randbelow(10 ** digits):0{digits}d}"


def create_student_account(*, matric_number, first_name, last_name, email, department, entry_level, **optional_fields):
    """Creates the User+StudentProfile and issues a PIN, returning (profile, raw_pin).

    The raw PIN only ever exists at this call site - only pin_hash gets persisted, so the
    caller must email raw_pin to the student immediately, since it can't be recovered later.
    """
    matric_number = matric_number.strip().upper()
    # Django's username field rejects "/", which real matric numbers contain (e.g.
    # 2023/CSC/030), so this is just an internal ID - actual student login goes through
    # the username Django already generates here (or, historically, matric-number lookup -
    # that fallback has been removed, login is username+password only now).
    username = matric_number.replace("/", "")

    user = User.objects.create_user(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=settings.DEFAULT_PASSWORD,
    )
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])

    student_group = Group.objects.get(name=STUDENT_GROUP)
    user.groups.add(student_group)

    profile = StudentProfile.objects.create(
        user=user,
        matric_number=matric_number,
        department=department,
        entry_level=entry_level,
        entry_session=settings.CURRENT_SESSION,
        **optional_fields,
    )

    raw_pin = generate_pin()
    profile.set_pin(raw_pin)
    profile.save(update_fields=["pin_hash"])

    return profile, raw_pin
