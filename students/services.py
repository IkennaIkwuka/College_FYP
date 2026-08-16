import secrets

from accounts.models import STUDENT_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from lu_sims.id_format import format_academic_id

from .models import StudentProfile


def generate_pin(digits=6):
    """Cryptographically-random numeric PIN, zero-padded, e.g. '004821'."""
    return f"{secrets.randbelow(10 ** digits):0{digits}d}"


def send_pin_email(profile, raw_pin):
    send_mail(
        subject="Your LU-SIMS PIN",
        message=(
            f"Matric number: {profile.matric_number}\n"
            f"PIN: {raw_pin}\n\n"
            f'Log in with your username "{profile.user.username}" and the '
            f'default password "{settings.DEFAULT_PASSWORD}", then enter this '
            "PIN when prompted to verify it's you."
        ),
        from_email=None,
        recipient_list=[profile.user.email],
    )


def create_student_account(*, matric_number, first_name, last_name, email, department, entry_level, **optional_fields):
    """Creates the User+StudentProfile, returning the profile.

    No PIN is issued here - the student requests one themselves at first login
    (accounts:send_pin_code), so it's never sitting unused in an old email.
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

    return profile


def reset_student_pin(profile):
    """Issues a fresh PIN and clears any lockout, returning the raw PIN to email.

    Always safe to call regardless of current lockout state - a fresh PIN makes
    whatever the student had before (forgotten, never received, or still valid)
    moot either way.
    """
    raw_pin = generate_pin()
    profile.set_pin(raw_pin)
    profile.failed_pin_attempts = 0
    profile.pin_locked_until = None
    profile.save(update_fields=["pin_hash", "failed_pin_attempts", "pin_locked_until"])
    return raw_pin
