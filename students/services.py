from accounts.models import STUDENT_GROUP, User
from django.contrib.auth.models import Group

from .models import StudentProfile


def create_student_account(*, matric_number, first_name, last_name, email, department, level, **optional_fields):
    matric_number = matric_number.strip().upper()
    username = matric_number.replace("/", "")

    user = User.objects.create_user(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=matric_number,
    )
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])

    student_group = Group.objects.get(name=STUDENT_GROUP)
    user.groups.add(student_group)

    return StudentProfile.objects.create(
        user=user,
        matric_number=matric_number,
        department=department,
        level=level,
        **optional_fields,
    )
