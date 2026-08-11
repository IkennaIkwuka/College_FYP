from accounts.models import STUDENT_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group

from .models import StudentProfile


def create_student_account(*, matric_number, first_name, last_name, email, department, entry_level, **optional_fields):
    matric_number = matric_number.strip().upper()
    # Django's username field rejects "/", which real matric numbers contain (e.g.
    # 2023/CSC/030), so this is just an internal ID - actual student login goes through
    # accounts.backends.MatricNumberOrUsernameBackend matching on the matric number itself.
    username = matric_number.replace("/", "")

    user = User.objects.create_user(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=settings.DEFAULT_STUDENT_PASSWORD,
    )
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])

    student_group = Group.objects.get(name=STUDENT_GROUP)
    user.groups.add(student_group)

    return StudentProfile.objects.create(
        user=user,
        matric_number=matric_number,
        department=department,
        entry_level=entry_level,
        entry_session=settings.CURRENT_SESSION,
        **optional_fields,
    )
