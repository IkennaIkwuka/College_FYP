from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from accounts.models import LECTURER_GROUP
from students.models import LEVEL_CHOICES, Department, StudentProfile

SEMESTER_CHOICES = [
    ("first", "First Semester"),
    ("second", "Second Semester"),
]


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    units = models.PositiveSmallIntegerField()
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="courses")
    level = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES)
    semester = models.CharField(max_length=6, choices=SEMESTER_CHOICES)
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses_taught",
        limit_choices_to={"groups__name": LECTURER_GROUP},
    )

    class Meta:
        ordering = ["code"]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.title}"


class CourseRegistration(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="registrations")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="registrations")
    session = models.CharField(max_length=9, help_text="e.g. 2025/2026")
    semester = models.CharField(max_length=6, choices=SEMESTER_CHOICES)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "course", "session", "semester")
        ordering = ["-session", "semester", "student"]

    def clean(self):
        # clean() isn't called automatically on save() - Django only runs it when
        # something calls full_clean() first (ModelForms/the admin do this for you).
        # It's still worth having here as the one place this rule is enforced,
        # rather than repeating the same check in every view that creates a registration.
        if self.course_id and self.student_id:
            if self.course.department_id != self.student.department_id:
                raise ValidationError("Course department must match the student's department.")
            if self.course.level != self.student.current_level:
                raise ValidationError("Course level must match the student's current level.")

    def __str__(self):
        return f"{self.student} - {self.course} ({self.session} {self.semester})"
