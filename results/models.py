from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from courses.models import CourseRegistration

GRADE_CHOICES = [
    ("A", "A"),
    ("B", "B"),
    ("C", "C"),
    ("D", "D"),
    ("E", "E"),
    ("F", "F"),
]

# NUC's real 5-point scale, not a 4.0 GPA - band lookup on an already-final,
# already-approved score (see results/services.py for how these feed GPA/CGPA).
GRADE_BANDS = [
    (70, "A", 5),
    (60, "B", 4),
    (50, "C", 3),
    (45, "D", 2),
    (40, "E", 1),
    (0, "F", 0),
]


def grade_for_score(score):
    for floor, letter, point in GRADE_BANDS:
        if score >= floor:
            return letter, point
    raise ValueError(f"score {score} did not match any grade band")


class Result(models.Model):
    registration = models.OneToOneField(CourseRegistration, on_delete=models.CASCADE, related_name="result")
    score = models.PositiveSmallIntegerField()
    grade = models.CharField(max_length=1, choices=GRADE_CHOICES, editable=False)
    grade_point = models.PositiveSmallIntegerField(editable=False)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="results_entered",
    )
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.score is not None and not (0 <= self.score <= 100):
            raise ValidationError("Score must be between 0 and 100.")

    def save(self, *args, **kwargs):
        # Score is entered directly via a plain Form (not a ModelForm), so nothing
        # calls full_clean() for us - checking here, same as Course.save() does for
        # its own level-vs-department-duration rule, is the backstop that actually runs.
        self.clean()
        self.grade, self.grade_point = grade_for_score(self.score)
        # update_or_create()'s update path calls save(update_fields={"score", ...}) -
        # grade/grade_point are always derived from score, so they'd silently go stale
        # on a correction unless explicitly added to whatever update_fields was passed.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"grade", "grade_point"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.registration} - {self.grade} ({self.score})"
