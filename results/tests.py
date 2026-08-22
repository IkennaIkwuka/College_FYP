from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from courses.models import Course, CourseRegistration
from courses.tests import make_hod, make_lecturer, make_student
from students.models import Department

from .models import Result, grade_for_score
from .services import compute_gpa, degree_classification


class GradeForScoreTests(TestCase):
    def test_band_boundaries(self):
        cases = [
            (0, ("F", 0)),
            (39, ("F", 0)),
            (40, ("E", 1)),
            (44, ("E", 1)),
            (45, ("D", 2)),
            (49, ("D", 2)),
            (50, ("C", 3)),
            (59, ("C", 3)),
            (60, ("B", 4)),
            (69, ("B", 4)),
            (70, ("A", 5)),
            (100, ("A", 5)),
        ]
        for score, expected in cases:
            self.assertEqual(grade_for_score(score), expected, f"score={score}")


class ComputeGpaTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = make_student("2023/CSC/001", self.department, 300)
        self.lecturer = make_lecturer("lect1")
        self.course_3units = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first", lecturer=self.lecturer,
        )
        self.course_2units = Course.objects.create(
            code="CSC303", title="Databases", units=2,
            department=self.department, level=300, semester="first", lecturer=self.lecturer,
        )

    def test_zero_results_gives_zero(self):
        self.assertEqual(compute_gpa(Result.objects.none()), 0.0)

    def test_single_result(self):
        registration = CourseRegistration.objects.create(
            student=self.profile, course=self.course_3units, session="2025/2026", semester="first",
        )
        Result.objects.create(registration=registration, score=75)  # A, 5 points
        self.assertEqual(compute_gpa(Result.objects.all()), 5.0)

    def test_multiple_results_weighted_by_units(self):
        reg_a = CourseRegistration.objects.create(
            student=self.profile, course=self.course_3units, session="2025/2026", semester="first",
        )
        reg_b = CourseRegistration.objects.create(
            student=self.profile, course=self.course_2units, session="2025/2026", semester="first",
        )
        Result.objects.create(registration=reg_a, score=75)  # A, 5 points, 3 units -> 15
        Result.objects.create(registration=reg_b, score=55)  # C, 3 points, 2 units -> 6
        # (15 + 6) / (3 + 2) = 4.2
        self.assertEqual(compute_gpa(Result.objects.all()), 4.2)


class DegreeClassificationTests(TestCase):
    def test_band_boundaries(self):
        cases = [
            (5.00, "First Class Honours"),
            (4.50, "First Class Honours"),
            (4.49, "Second Class Honours (Upper Division)"),
            (3.50, "Second Class Honours (Upper Division)"),
            (3.49, "Second Class Honours (Lower Division)"),
            (2.40, "Second Class Honours (Lower Division)"),
            (2.39, "Third Class Honours"),
            (1.50, "Third Class Honours"),
            (1.49, "Pass"),
            (1.00, "Pass"),
            (0.99, "Below Pass Mark"),
        ]
        for cgpa, expected in cases:
            self.assertEqual(degree_classification(cgpa), expected, f"cgpa={cgpa}")


def _formset_post_data(rows, prefix="form"):
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for i, (registration_id, score) in enumerate(rows):
        data[f"{prefix}-{i}-registration_id"] = str(registration_id)
        if score is not None:
            data[f"{prefix}-{i}-score"] = str(score)
    return data


class CourseResultsEntryTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.other_department = Department.objects.create(name="Physics")
        self.lecturer = make_lecturer("lect1")
        self.other_lecturer = make_lecturer("lect2")
        self.hod = make_hod("hod1", department=self.department)
        self.other_hod = make_hod("hod2", department=self.other_department)
        self.student = make_student("2023/CSC/001", self.department, 300)

        self.course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first", lecturer=self.lecturer,
        )
        self.registration = CourseRegistration.objects.create(
            student=self.student, course=self.course, session="2025/2026", semester="first",
        )
        self.url = reverse("results:course_results_entry", args=[self.course.id])

    def test_owning_lecturer_can_enter_score(self):
        self.client.login(username="lect1", password="pass12345")
        response = self.client.post(
            f"{self.url}?session=2025/2026",
            _formset_post_data([(self.registration.id, 75)]),
        )
        self.assertRedirects(response, f"{self.url}?session=2025/2026", fetch_redirect_response=False)
        result = Result.objects.get(registration=self.registration)
        self.assertEqual(result.score, 75)
        self.assertEqual(result.grade, "A")
        self.assertEqual(result.entered_by, self.lecturer)

    def test_non_owning_lecturer_forbidden(self):
        self.client.login(username="lect2", password="pass12345")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_hod_can_enter_score_for_department_course(self):
        self.client.login(username="hod1", password="pass12345")
        response = self.client.post(
            f"{self.url}?session=2025/2026",
            _formset_post_data([(self.registration.id, 60)]),
        )
        self.assertRedirects(response, f"{self.url}?session=2025/2026", fetch_redirect_response=False)
        result = Result.objects.get(registration=self.registration)
        self.assertEqual(result.grade, "B")
        self.assertEqual(result.entered_by, self.hod)

    def test_hod_from_other_department_forbidden(self):
        self.client.login(username="hod2", password="pass12345")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_student_forbidden(self):
        self.client.login(username=self.student.user.username, password=settings.DEFAULT_PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_resubmitting_updates_not_duplicates(self):
        self.client.login(username="lect1", password="pass12345")
        self.client.post(f"{self.url}?session=2025/2026", _formset_post_data([(self.registration.id, 55)]))
        self.client.post(f"{self.url}?session=2025/2026", _formset_post_data([(self.registration.id, 80)]))
        self.assertEqual(Result.objects.filter(registration=self.registration).count(), 1)
        result = Result.objects.get(registration=self.registration)
        self.assertEqual(result.score, 80)
        self.assertEqual(result.grade, "A")


class MyResultsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.lecturer = make_lecturer("lect1")
        self.student = make_student("2023/CSC/001", self.department, 300)
        self.other_student = make_student("2023/CSC/002", self.department, 300)

        self.course_3units = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first", lecturer=self.lecturer,
        )
        self.course_2units = Course.objects.create(
            code="CSC303", title="Databases", units=2,
            department=self.department, level=300, semester="first", lecturer=self.lecturer,
        )

        reg_a = CourseRegistration.objects.create(
            student=self.student, course=self.course_3units, session="2025/2026", semester="first",
        )
        reg_b = CourseRegistration.objects.create(
            student=self.student, course=self.course_2units, session="2025/2026", semester="first",
        )
        Result.objects.create(registration=reg_a, score=75)  # A, 5 -> 15 points
        Result.objects.create(registration=reg_b, score=55)  # C, 3 -> 6 points

        other_reg = CourseRegistration.objects.create(
            student=self.other_student, course=self.course_3units, session="2025/2026", semester="first",
        )
        Result.objects.create(registration=other_reg, score=40)

    def test_student_sees_own_results_with_correct_cgpa(self):
        self.client.login(username=self.student.user.username, password=settings.DEFAULT_PASSWORD)
        response = self.client.get(reverse("results:my_results"))
        self.assertContains(response, "CSC301")
        self.assertContains(response, "CSC303")
        # (15 + 6) / (3 + 2) = 4.2
        self.assertEqual(response.context["cgpa"], 4.2)
        self.assertEqual(response.context["classification"], "Second Class Honours (Upper Division)")

    def test_does_not_see_other_students_results(self):
        self.client.login(username=self.student.user.username, password=settings.DEFAULT_PASSWORD)
        response = self.client.get(reverse("results:my_results"))
        self.assertNotContains(response, "2023/CSC/002")

    def test_non_student_forbidden(self):
        self.client.login(username="lect1", password="pass12345")
        response = self.client.get(reverse("results:my_results"))
        self.assertEqual(response.status_code, 403)
