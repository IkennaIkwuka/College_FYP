from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from students.models import Department
from students.services import create_student_account
from students.tests import make_admin

from .models import Course, CourseRegistration


def make_student(matric_number, department, level):
    profile = create_student_account(
        matric_number=matric_number,
        first_name="Test",
        last_name="Student",
        email=f"{matric_number.replace('/', '').lower()}@example.com",
        department=department,
        entry_level=level,
    )
    profile.user.must_change_password = False
    profile.user.save(update_fields=["must_change_password"])
    return profile


class RegisterViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.other_department = Department.objects.create(name="Physics")
        self.profile = make_student("2023/CSC/001", self.department, 300)

        self.matching_course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first",
        )
        self.wrong_department_course = Course.objects.create(
            code="PHY301", title="Mechanics", units=3,
            department=self.other_department, level=300, semester="first",
        )
        self.wrong_level_course = Course.objects.create(
            code="CSC201", title="Data Structures", units=3,
            department=self.department, level=200, semester="first",
        )
        self.wrong_semester_course = Course.objects.create(
            code="CSC302", title="Compilers", units=3,
            department=self.department, level=300, semester="second",
        )

        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_STUDENT_PASSWORD)

    def test_no_query_params_shows_semester_form(self):
        response = self.client.get(reverse("courses:register"))
        self.assertTemplateUsed(response, "courses/select_semester.html")

    def test_valid_semester_shows_course_list(self):
        response = self.client.get(reverse("courses:register"), {"semester": "first"})
        self.assertTemplateUsed(response, "courses/select_courses.html")

    def test_step_two_only_lists_matching_available_courses(self):
        response = self.client.get(reverse("courses:register"), {"semester": "first"}, follow=True)
        available = list(response.context["form"].fields["courses"].queryset)
        self.assertEqual(available, [self.matching_course])

    def test_post_creates_registration(self):
        url = f"{reverse('courses:register')}?semester=first"
        response = self.client.post(url, {"courses": [self.matching_course.id]})
        self.assertRedirects(response, reverse("courses:my_registrations"))
        self.assertTrue(
            CourseRegistration.objects.filter(
                student=self.profile,
                course=self.matching_course,
                session=settings.CURRENT_SESSION,
                semester="first",
            ).exists()
        )

    def test_already_registered_course_excluded_from_available_list(self):
        CourseRegistration.objects.create(
            student=self.profile,
            course=self.matching_course,
            session=settings.CURRENT_SESSION,
            semester="first",
        )
        response = self.client.get(reverse("courses:register"), {"semester": "first"}, follow=True)
        available = list(response.context["form"].fields["courses"].queryset)
        self.assertEqual(available, [])

    def test_registration_follows_current_level_not_entry_level(self):
        freshman = make_student("2023/CSC/003", self.department, 100)
        hundred_level_course = Course.objects.create(
            code="CSC101", title="Intro to Programming", units=3,
            department=self.department, level=100, semester="first",
        )
        self.client.login(username=freshman.user.username, password=settings.DEFAULT_STUDENT_PASSWORD)

        with override_settings(CURRENT_SESSION="2027/2028"):
            response = self.client.get(reverse("courses:register"), {"semester": "first"}, follow=True)
            available = list(response.context["form"].fields["courses"].queryset)
            self.assertEqual(available, [self.matching_course])
            self.assertNotIn(hundred_level_course, available)

    def test_non_student_gets_403(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:register"))
        self.assertEqual(response.status_code, 403)


class MyRegistrationsViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = make_student("2023/CSC/002", self.department, 300)
        self.course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first",
        )
        CourseRegistration.objects.create(
            student=self.profile, course=self.course, session=settings.CURRENT_SESSION, semester="first"
        )
        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_STUDENT_PASSWORD)

    def test_lists_own_registrations(self):
        response = self.client.get(reverse("courses:my_registrations"))
        self.assertContains(response, "CSC301")
        self.assertContains(response, settings.CURRENT_SESSION)
