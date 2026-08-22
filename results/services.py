from .models import Result

DEGREE_CLASSIFICATION_BANDS = [
    (4.50, "First Class Honours"),
    (3.50, "Second Class Honours (Upper Division)"),
    (2.40, "Second Class Honours (Lower Division)"),
    (1.50, "Third Class Honours"),
    (1.00, "Pass"),
]


def compute_gpa(result_queryset):
    """Unit-weighted average grade point over a queryset of Result rows.

    Works for both a single semester's SGPA and a student's full CGPA - the
    caller controls the scope by how the queryset is filtered.
    """
    total_units = 0
    total_points = 0
    for result in result_queryset.select_related("registration__course"):
        units = result.registration.course.units
        total_units += units
        total_points += units * result.grade_point
    if total_units == 0:
        return 0.0
    return round(total_points / total_units, 2)


def compute_cgpa(student_profile):
    results = Result.objects.filter(registration__student=student_profile)
    return compute_gpa(results)


def degree_classification(cgpa):
    for floor, label in DEGREE_CLASSIFICATION_BANDS:
        if cgpa >= floor:
            return label
    return "Below Pass Mark"
