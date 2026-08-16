from accounts.models import HOD_GROUP, LECTURER_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from students.models import Department
from students.services import create_student_account
from students.tests import make_admin

from .models import Course, CourseRegistration


def make_hod(username, department=None):
    hod = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    hod.groups.add(Group.objects.get(name=HOD_GROUP))
    if department is not None:
        department.hod = hod
        department.save(update_fields=["hod"])
    return hod


def make_lecturer(username):
    lecturer = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    lecturer.groups.add(Group.objects.get(name=LECTURER_GROUP))
    return lecturer


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
        self.carryover_course = Course.objects.create(
            code="CSC201", title="Data Structures", units=3,
            department=self.department, level=200, semester="first",
        )
        self.wrong_department_course = Course.objects.create(
            code="PHY301", title="Mechanics", units=3,
            department=self.other_department, level=300, semester="first",
        )
        self.above_current_level_course = Course.objects.create(
            code="CSC401", title="Distributed Systems", units=3,
            department=self.department, level=400, semester="first",
        )
        self.wrong_semester_course = Course.objects.create(
            code="CSC302", title="Compilers", units=3,
            department=self.department, level=300, semester="second",
        )

        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)

    def test_get_shows_course_list_directly(self):
        response = self.client.get(reverse("courses:register"))
        self.assertTemplateUsed(response, "courses/register.html")

    def test_lists_own_level_and_lower_levels_but_not_above(self):
        response = self.client.get(reverse("courses:register"))
        available = set(response.context["form"].fields["courses"].queryset)
        self.assertEqual(available, {self.matching_course, self.carryover_course})

    def test_post_creates_registration(self):
        response = self.client.post(reverse("courses:register"), {"courses": [self.matching_course.id]})
        self.assertRedirects(response, reverse("courses:my_registrations"))
        self.assertTrue(
            CourseRegistration.objects.filter(
                student=self.profile,
                course=self.matching_course,
                session=settings.CURRENT_SESSION,
                semester=settings.CURRENT_SEMESTER,
            ).exists()
        )

    def test_can_actually_register_for_carryover_course(self):
        # Proves the lower-level course isn't just shown but genuinely registerable -
        # would have failed if CourseRegistration.clean() still required exact level equality.
        response = self.client.post(reverse("courses:register"), {"courses": [self.carryover_course.id]})
        self.assertRedirects(response, reverse("courses:my_registrations"))
        self.assertTrue(
            CourseRegistration.objects.filter(student=self.profile, course=self.carryover_course).exists()
        )

    def test_already_registered_course_excluded_from_available_list(self):
        CourseRegistration.objects.create(
            student=self.profile,
            course=self.matching_course,
            session=settings.CURRENT_SESSION,
            semester=settings.CURRENT_SEMESTER,
        )
        response = self.client.get(reverse("courses:register"))
        available = list(response.context["form"].fields["courses"].queryset)
        self.assertEqual(available, [self.carryover_course])

    def test_registration_follows_current_level_not_entry_level(self):
        freshman = make_student("2023/CSC/003", self.department, 100)
        self.client.login(username=freshman.user.username, password=settings.DEFAULT_PASSWORD)

        with override_settings(CURRENT_SESSION="2027/2028"):
            # Two sessions later, entry_level 100 -> current_level 300 - the 300-level
            # course should now be visible even though it wasn't at their entry level.
            response = self.client.get(reverse("courses:register"))
            available = set(response.context["form"].fields["courses"].queryset)
            self.assertIn(self.matching_course, available)
            self.assertNotIn(self.above_current_level_course, available)

    def test_non_student_gets_403(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:register"))
        self.assertEqual(response.status_code, 403)

    def test_inactive_course_excluded_from_available_list(self):
        self.matching_course.is_active = False
        self.matching_course.save(update_fields=["is_active"])
        response = self.client.get(reverse("courses:register"))
        available = set(response.context["form"].fields["courses"].queryset)
        self.assertNotIn(self.matching_course, available)


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
        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)

    def test_lists_own_registrations(self):
        response = self.client.get(reverse("courses:my_registrations"))
        self.assertContains(response, "CSC301")
        self.assertContains(response, settings.CURRENT_SESSION)


class ManageCoursesTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.other_department = Department.objects.create(name="Physics")
        self.hod = make_hod("hod1", department=self.department)
        self.other_hod = make_hod("hod2", department=self.other_department)

        self.own_course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first",
        )
        self.other_course = Course.objects.create(
            code="PHY301", title="Mechanics", units=3,
            department=self.other_department, level=300, semester="first",
        )

        self.client.login(username="hod1", password="pass12345")

    def test_manage_courses_lists_only_own_department(self):
        response = self.client.get(reverse("courses:manage_courses"))
        self.assertContains(response, "CSC301")
        self.assertNotContains(response, "PHY301")

    def test_filter_by_level(self):
        Course.objects.create(
            code="CSC101", title="Intro", units=3,
            department=self.department, level=100, semester="first",
        )
        response = self.client.get(reverse("courses:manage_courses"), {"level": 100})
        self.assertContains(response, "CSC101")
        self.assertNotContains(response, "CSC301")

    def test_filter_by_semester(self):
        Course.objects.create(
            code="CSC303", title="Compilers", units=3,
            department=self.department, level=300, semester="second",
        )
        response = self.client.get(reverse("courses:manage_courses"), {"semester": "second"})
        self.assertContains(response, "CSC303")
        self.assertNotContains(response, "CSC301")

    def test_filter_by_active_status(self):
        inactive = Course.objects.create(
            code="CSC199", title="Retired", units=3,
            department=self.department, level=100, semester="first", is_active=False,
        )
        response = self.client.get(reverse("courses:manage_courses"), {"is_active": "0"})
        self.assertContains(response, "CSC199")
        self.assertNotContains(response, "CSC301")

    def test_pagination_limits_to_ten_per_page(self):
        for i in range(20):
            Course.objects.create(
                code=f"CSC1{i:02d}", title=f"Extra {i}", units=3,
                department=self.department, level=100, semester="first",
            )
        response = self.client.get(reverse("courses:manage_courses"))
        self.assertEqual(len(response.context["courses"]), 10)

        response_page2 = self.client.get(reverse("courses:manage_courses"), {"page": 2})
        self.assertEqual(response_page2.context["courses"].number, 2)

    def test_add_course_is_scoped_to_own_department(self):
        response = self.client.post(
            reverse("courses:course_add"),
            {"code": "CSC302", "title": "Compilers", "units": 3, "level": 300, "semester": "first"},
        )
        self.assertRedirects(response, reverse("courses:manage_courses"))
        course = Course.objects.get(code="CSC302")
        self.assertEqual(course.department, self.department)

    def test_edit_own_course_succeeds(self):
        response = self.client.post(
            reverse("courses:course_edit", args=[self.own_course.id]),
            {"code": "CSC301", "title": "Algorithms II", "units": 3, "level": 300, "semester": "first"},
        )
        self.assertRedirects(response, reverse("courses:manage_courses"))
        self.own_course.refresh_from_db()
        self.assertEqual(self.own_course.title, "Algorithms II")

    def test_edit_other_departments_course_404s(self):
        response = self.client.get(reverse("courses:course_edit", args=[self.other_course.id]))
        self.assertEqual(response.status_code, 404)

    def test_toggle_active_on_other_departments_course_404s(self):
        response = self.client.post(reverse("courses:course_toggle_active", args=[self.other_course.id]))
        self.assertEqual(response.status_code, 404)

    def test_toggle_active_deactivates_and_removes_from_student_registration(self):
        student = make_student("2023/CSC/010", self.department, 300)
        self.client.post(reverse("courses:course_toggle_active", args=[self.own_course.id]))
        self.own_course.refresh_from_db()
        self.assertFalse(self.own_course.is_active)

        self.client.login(username=student.user.username, password=settings.DEFAULT_PASSWORD)
        response = self.client.get(reverse("courses:register"))
        available = set(response.context["form"].fields["courses"].queryset)
        self.assertNotIn(self.own_course, available)

    def test_hod_with_no_department_sees_friendly_message(self):
        make_hod("hod_unassigned")
        self.client.login(username="hod_unassigned", password="pass12345")
        response = self.client.get(reverse("courses:manage_courses"))
        self.assertContains(response, "not assigned as HOD")

    def test_non_hod_gets_403(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:manage_courses"))
        self.assertEqual(response.status_code, 403)


class CourseRegistrationsViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.other_department = Department.objects.create(name="Physics")
        self.hod = make_hod("hod1", department=self.department)

        self.own_course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first",
        )
        self.other_course = Course.objects.create(
            code="PHY301", title="Mechanics", units=3,
            department=self.other_department, level=300, semester="first",
        )
        self.student = make_student("2023/CSC/050", self.department, 300)
        CourseRegistration.objects.create(
            student=self.student, course=self.own_course,
            session=settings.CURRENT_SESSION, semester="first",
        )
        self.other_student = make_student("2023/CSC/051", self.department, 300)
        CourseRegistration.objects.create(
            student=self.other_student, course=self.own_course,
            session="2020/2021", semester="second",
        )

        self.client.login(username="hod1", password="pass12345")

    def test_shows_registrations_for_own_course(self):
        response = self.client.get(reverse("courses:course_registrations", args=[self.own_course.id]))
        self.assertContains(response, "2023/CSC/050")

    def test_filter_by_session(self):
        response = self.client.get(
            reverse("courses:course_registrations", args=[self.own_course.id]), {"session": "2020/2021"}
        )
        self.assertContains(response, "2023/CSC/051")
        self.assertNotContains(response, "2023/CSC/050")

    def test_filter_by_semester(self):
        response = self.client.get(
            reverse("courses:course_registrations", args=[self.own_course.id]), {"semester": "second"}
        )
        self.assertContains(response, "2023/CSC/051")
        self.assertNotContains(response, "2023/CSC/050")

    def test_pagination_limits_to_ten_per_page(self):
        for i in range(15):
            extra_student = make_student(f"2024/CSC/{i:03d}", self.department, 300)
            CourseRegistration.objects.create(
                student=extra_student, course=self.own_course,
                session=settings.CURRENT_SESSION, semester="first",
            )
        response = self.client.get(reverse("courses:course_registrations", args=[self.own_course.id]))
        self.assertEqual(len(response.context["registrations"]), 10)

        response_page2 = self.client.get(
            reverse("courses:course_registrations", args=[self.own_course.id]), {"page": 2}
        )
        self.assertEqual(response_page2.context["registrations"].number, 2)

    def test_other_departments_course_404s(self):
        response = self.client.get(reverse("courses:course_registrations", args=[self.other_course.id]))
        self.assertEqual(response.status_code, 404)

    def test_non_hod_gets_403(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:course_registrations", args=[self.own_course.id]))
        self.assertEqual(response.status_code, 403)


class MyCoursesTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.lecturer = make_lecturer("lect1")
        self.other_lecturer = make_lecturer("lect2")

        self.own_course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first", lecturer=self.lecturer,
        )
        self.other_course = Course.objects.create(
            code="CSC302", title="Compilers", units=3,
            department=self.department, level=300, semester="first", lecturer=self.other_lecturer,
        )

        self.client.login(username="lect1", password="pass12345")

    def test_lists_only_own_courses(self):
        response = self.client.get(reverse("courses:my_courses"))
        self.assertContains(response, "CSC301")
        self.assertNotContains(response, "CSC302")

    def test_non_lecturer_gets_403(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:my_courses"))
        self.assertEqual(response.status_code, 403)
