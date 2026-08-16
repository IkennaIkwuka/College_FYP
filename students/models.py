from datetime import timedelta

from accounts.models import DEAN_GROUP, HOD_GROUP
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

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

ADMISSION_TYPE_CHOICES = [
    ("UTME", "UTME (Regular Entry)"),
    ("DE", "Direct Entry"),
    ("TRANSFER_INTRA", "Transfer (Intra-Faculty)"),
    ("TRANSFER_INTER", "Transfer (Inter-Faculty)"),
]


class Faculty(models.Model):
    name = models.CharField(max_length=100, unique=True)
    dean = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faculty_headed",
        limit_choices_to={"groups__name": DEAN_GROUP},
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "faculties"

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments",
    )
    hod = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_headed",
        limit_choices_to={"groups__name": HOD_GROUP},
    )

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
    # Level and session the student joined at - never updated after creation. Current level
    # is derived from these (see current_level below) rather than stored, so it advances on
    # its own every time settings.CURRENT_SESSION is bumped for a new academic year.
    entry_level = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES)
    entry_session = models.CharField(max_length=9, help_text="e.g. 2025/2026")
    admission_type = models.CharField(max_length=20, choices=ADMISSION_TYPE_CHOICES, default="UTME")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    # PIN emailed at account-creation time - proves the student owns the email on file
    # before the shared, guessable DEFAULT_PASSWORD gets replaced with something only
    # they know. Same hashing/lockout mechanics the old AdmissionRecord used for
    # self-registration, just living on the account itself now that IT Admin creates
    # every student account directly instead of a public self-service flow doing it.
    pin_hash = models.CharField(max_length=128, blank=True, default="")
    failed_pin_attempts = models.PositiveSmallIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.matric_number = self.matric_number.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.matric_number} - {self.user.get_full_name() or self.user.username}"

    @property
    def current_level(self):
        entry_year = int(self.entry_session.split("/")[0])
        current_year = int(settings.CURRENT_SESSION.split("/")[0])
        years_elapsed = current_year - entry_year
        return min(self.entry_level + years_elapsed * 100, LEVEL_CHOICES[-1][0])

    @property
    def current_level_display(self):
        return dict(LEVEL_CHOICES).get(self.current_level, self.current_level)

    def set_pin(self, raw_pin):
        self.pin_hash = make_password(raw_pin)

    def check_pin(self, raw_pin):
        return check_password(raw_pin, self.pin_hash)

    @property
    def is_pin_locked(self):
        return self.pin_locked_until is not None and self.pin_locked_until > timezone.now()

    def register_failed_pin_attempt(self):
        self.failed_pin_attempts += 1
        if self.failed_pin_attempts >= settings.PIN_MAX_ATTEMPTS:
            self.pin_locked_until = timezone.now() + timedelta(minutes=settings.PIN_LOCKOUT_MINUTES)
        self.save(update_fields=["failed_pin_attempts", "pin_locked_until"])

    def reset_pin_attempts(self):
        self.failed_pin_attempts = 0
        self.pin_locked_until = None
        self.save(update_fields=["failed_pin_attempts", "pin_locked_until"])
