from django.contrib.auth.models import AbstractUser
from django.db import models

ADMIN_GROUP = "IT Admin"
LECTURER_GROUP = "Lecturer"
STUDENT_GROUP = "Student"
HOD_GROUP = "HOD"
REGISTRAR_GROUP = "Registrar"
BURSAR_GROUP = "Bursar"
DEAN_GROUP = "Dean"


class User(AbstractUser):
    """Custom user model so role/permission logic isn't locked to Django's default auth.User."""

    email = models.EmailField(unique=True)
    must_change_password = models.BooleanField(default=False)
    # Only set for staff (Lecturer/HOD/IT Admin) - students are identified by
    # StudentProfile.matric_number instead. null=True (not just blank) so every
    # student's staff_id being empty doesn't collide under the unique constraint -
    # SQL treats multiple NULLs as non-conflicting, unlike multiple empty strings.
    staff_id = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def has_role(self, group_name):
        return self.groups.filter(name=group_name).exists()

    @property
    def is_admin(self):
        return self.is_superuser or self.has_role(ADMIN_GROUP)

    @property
    def is_lecturer(self):
        return self.has_role(LECTURER_GROUP)

    @property
    def is_student(self):
        return self.has_role(STUDENT_GROUP)

    @property
    def is_hod(self):
        return self.has_role(HOD_GROUP)

    @property
    def is_registrar(self):
        return self.has_role(REGISTRAR_GROUP)

    @property
    def is_bursar(self):
        return self.has_role(BURSAR_GROUP)

    @property
    def is_dean(self):
        return self.has_role(DEAN_GROUP)
