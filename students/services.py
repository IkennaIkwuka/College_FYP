import secrets

from accounts.models import STUDENT_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group
from lu_sims.id_format import format_academic_id

from .models import StudentProfile


def generate_pin(digits=6):
    """Cryptographically-random numeric PIN, zero-padded, e.g. '004821'."""
    return f"{secrets.randbelow(10 ** digits):0{digits}d}"


def create_student_account(*, matric_number, first_name, last_name, email, department, entry_level, **optional_fields):
    """Creates the User+StudentProfile and issues a PIN, returning (profile, raw_pin).

    The raw PIN only ever exists at this call site - only pin_hash gets persisted, so the
    caller must email raw_pin to the student immediately, since it can't be recovered later.
    """
    matric_number = format_academic_id(matric_number)
    # Django's username field rejects "/", which real matric numbers contain (e.g.
    # 2023/CSC/030), so this is just an internal ID - LenientUsernameBackend
    # (accounts/auth_backends.py) is what actually lets a student log in typing
    # the matric number in its natural shape instead of this stripped/lowercased form.
    username = matric_number.replace("/", "").lower()

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
