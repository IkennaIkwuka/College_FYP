from django.contrib.auth.models import AbstractUser
from django.db import models

ADMIN_GROUP = "Admin"
LECTURER_GROUP = "Lecturer"
STUDENT_GROUP = "Student"


class User(AbstractUser):
    """Custom user model so role/permission logic isn't locked to Django's default auth.User."""

    email = models.EmailField(unique=True)

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
