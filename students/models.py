from django.conf import settings
from django.db import models

LEVEL_CHOICES = [
    (100, "100 Level"),
    (200, "200 Level"),
    (300, "300 Level"),
    (400, "400 Level"),
    (500, "500 Level"),
]

GENDER_CHOICES = [
    ("M", "Male"),
    ("F", "Female"),
]


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    matric_number = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="students")
    level = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.matric_number = self.matric_number.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.matric_number} - {self.user.get_full_name() or self.user.username}"
