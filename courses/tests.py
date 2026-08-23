from accounts.models import DEAN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from students.models import Department, Faculty
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


def make_registrar(username):
    registrar = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    registrar.groups.add(Group.objects.get(name=REGISTRAR_GROUP))
    return registrar


def make_dean(username, faculty=None):
    dean = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    dean.groups.add(Group.objects.get(name=DEAN_GROUP))
    if faculty is not None:
        faculty.dean = dean
        faculty.save(update_fields=["dean"])
    return dean


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

    def test_registering_over_max_units_is_rejected(self):
        over_course = Course.objects.create(
            code="CSC303", title="Big Course", units=22,
            department=self.department, level=300, semester="first",
        )
        response = self.client.post(
            reverse("courses:register"),
            {"courses": [self.matching_course.id, over_course.id]},  # 3 + 22 = 25 units
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CourseRegistration.objects.filter(student=self.profile, course=over_course).exists()
        )
        self.assertContains(response, "maximum allowed per semester")

    def test_registering_under_min_units_still_succeeds_with_warning(self):
        # follow=True so the flashed message can be checked on the same response -
        # messages are consumed on first render, and assertRedirects on its own
        # already renders (and would otherwise use up) the target page once.
        response = self.client.post(
            reverse("courses:register"), {"courses": [self.matching_course.id]}, follow=True
        )
        self.assertRedirects(response, reverse("courses:my_registrations"))
        self.assertTrue(
            CourseRegistration.objects.filter(student=self.profile, course=self.matching_course).exists()
        )
        self.assertContains(response, "NUC minimum is 15")


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
            code="CSC304", title="Compilers", units=3,
            department=self.department, level=300, semester="second",
        )
        response = self.client.get(reverse("courses:manage_courses"), {"semester": "second"})
        self.assertContains(response, "CSC304")
        self.assertNotContains(response, "CSC301")

    def test_defaults_to_current_semester(self):
        # settings.CURRENT_SEMESTER is "first" - with no explicit filter, a
        # next-semester course shouldn't show up alongside this semester's.
        Course.objects.create(
            code="CSC304", title="Compilers", units=3,
            department=self.department, level=300, semester="second",
        )
        response = self.client.get(reverse("courses:manage_courses"))
        self.assertContains(response, "CSC301")
        self.assertNotContains(response, "CSC304")

    def test_explicit_all_semesters_filter_still_shows_everything(self):
        # The default narrows to the current semester, but an HOD can still
        # deliberately ask to see every semester via the "All semesters" option.
        Course.objects.create(
            code="CSC304", title="Compilers", units=3,
            department=self.department, level=300, semester="second",
        )
        response = self.client.get(reverse("courses:manage_courses"), {"semester": ""})
        self.assertContains(response, "CSC301")
        self.assertContains(response, "CSC304")

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
            # *2+1 keeps every generated code's last digit odd, matching the
            # "first semester" code convention being enforced now.
            Course.objects.create(
                code=f"CSC1{(i * 2 + 1):02d}", title=f"Extra {i}", units=3,
                department=self.department, level=100, semester="first",
            )
        response = self.client.get(reverse("courses:manage_courses"))
        self.assertEqual(len(response.context["courses"]), 10)

        response_page2 = self.client.get(reverse("courses:manage_courses"), {"page": 2})
        self.assertEqual(response_page2.context["courses"].number, 2)

    def test_add_course_is_scoped_to_own_department(self):
        response = self.client.post(
            reverse("courses:course_add"),
            {"code": "CSC303", "title": "Compilers", "units": 3, "level": 300, "semester": "first"},
        )
        self.assertRedirects(response, reverse("courses:manage_courses"))
        course = Course.objects.get(code="CSC303")
        self.assertEqual(course.department, self.department)

    def test_add_course_rejects_semester_mismatched_code(self):
        response = self.client.post(
            reverse("courses:course_add"),
            {"code": "CSC302", "title": "Bad Code", "units": 3, "level": 300, "semester": "first"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Course.objects.filter(code="CSC302").exists())
        self.assertContains(response, "should end in an odd digit")

    def test_add_course_rejects_level_beyond_department_duration(self):
        # self.department has no explicit duration_years - defaults to 4, so a
        # 500 Level course should be rejected.
        response = self.client.post(
            reverse("courses:course_add"),
            {"code": "CSC501", "title": "Too Advanced", "units": 3, "level": 500, "semester": "first"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Course.objects.filter(code="CSC501").exists())
        self.assertContains(response, "4-year programme")

    def test_add_course_at_level_within_a_longer_departments_duration(self):
        law_department = Department.objects.create(name="Law", duration_years=5)
        make_hod("hod_law", department=law_department)
        self.client.logout()
        self.client.login(username="hod_law", password="pass12345")

        response = self.client.post(
            reverse("courses:course_add"),
            {"code": "LAW501", "title": "Advanced Law", "units": 3, "level": 500, "semester": "first"},
        )
        self.assertRedirects(response, reverse("courses:manage_courses"))
        self.assertTrue(Course.objects.filter(code="LAW501").exists())

    def test_edit_own_course_succeeds(self):
        response = self.client.post(
            reverse("courses:course_edit", args=[self.own_course.id]),
            {"code": "CSC301", "title": "Algorithms II", "units": 3, "level": 300, "semester": "first"},
        )
        self.assertRedirects(response, reverse("courses:course_detail", args=[self.own_course.id]))
        self.own_course.refresh_from_db()
        self.assertEqual(self.own_course.title, "Algorithms II")

    def test_edit_other_departments_course_404s(self):
        response = self.client.get(reverse("courses:course_edit", args=[self.other_course.id]))
        self.assertEqual(response.status_code, 404)

    def test_course_detail_shows_read_only_record(self):
        response = self.client.get(reverse("courses:course_detail", args=[self.own_course.id]))
        self.assertContains(response, "CSC301")
        self.assertContains(response, "Algorithms")
        self.assertContains(response, "Edit")

    def test_course_detail_other_departments_course_404s(self):
        response = self.client.get(reverse("courses:course_detail", args=[self.other_course.id]))
        self.assertEqual(response.status_code, 404)

    def test_course_detail_non_hod_forbidden(self):
        make_lecturer("lect_for_course_detail")
        self.client.logout()
        self.client.login(username="lect_for_course_detail", password="pass12345")
        response = self.client.get(reverse("courses:course_detail", args=[self.own_course.id]))
        self.assertEqual(response.status_code, 403)

    def test_manage_courses_list_links_to_detail_not_edit(self):
        response = self.client.get(reverse("courses:manage_courses"))
        self.assertContains(response, reverse("courses:course_detail", args=[self.own_course.id]))

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


class CourseCatalogTests(TestCase):
    def setUp(self):
        self.dept1 = Department.objects.create(name="Computer Science")
        self.dept2 = Department.objects.create(name="Physics")
        self.course1 = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.dept1, level=300, semester="first",
        )
        self.course2 = Course.objects.create(
            code="PHY301", title="Mechanics", units=3,
            department=self.dept2, level=300, semester="first",
        )
        make_registrar("reg1")
        self.client.login(username="reg1", password="pass12345")

    def test_shows_courses_from_multiple_departments(self):
        response = self.client.get(reverse("courses:course_catalog"))
        self.assertContains(response, "CSC301")
        self.assertContains(response, "PHY301")

    def test_filter_by_department(self):
        response = self.client.get(reverse("courses:course_catalog"), {"department": self.dept2.id})
        self.assertContains(response, "PHY301")
        self.assertNotContains(response, "CSC301")

    def test_non_registrar_gets_403(self):
        make_admin()
        self.client.logout()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:course_catalog"))
        self.assertEqual(response.status_code, 403)


class FacultyCoursesTests(TestCase):
    def setUp(self):
        self.faculty = Faculty.objects.create(name="Faculty of Science")
        self.other_faculty = Faculty.objects.create(name="Faculty of Arts")
        self.dept1 = Department.objects.create(name="Computer Science", faculty=self.faculty)
        self.dept2 = Department.objects.create(name="Physics", faculty=self.faculty)
        self.other_dept = Department.objects.create(name="History", faculty=self.other_faculty)

        self.own_course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.dept1, level=300, semester="first",
        )
        self.other_faculty_course = Course.objects.create(
            code="HIS301", title="World History", units=3,
            department=self.other_dept, level=300, semester="first",
        )

        make_dean("dean1", faculty=self.faculty)
        self.client.login(username="dean1", password="pass12345")

    def test_shows_own_faculty_courses_only(self):
        response = self.client.get(reverse("courses:faculty_courses"))
        self.assertContains(response, "CSC301")
        self.assertNotContains(response, "HIS301")

    def test_filter_by_department_within_faculty(self):
        Course.objects.create(
            code="PHY301", title="Mechanics", units=3,
            department=self.dept2, level=300, semester="first",
        )
        response = self.client.get(reverse("courses:faculty_courses"), {"department": self.dept1.id})
        self.assertContains(response, "CSC301")
        self.assertNotContains(response, "PHY301")

    def test_dean_with_no_faculty_sees_friendly_message(self):
        make_dean("dean_unassigned")
        self.client.logout()
        self.client.login(username="dean_unassigned", password="pass12345")
        response = self.client.get(reverse("courses:faculty_courses"))
        self.assertContains(response, "not assigned as Dean")

    def test_non_dean_gets_403(self):
        make_admin()
        self.client.logout()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:faculty_courses"))
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
            code="CSC303", title="Compilers", units=3,
            department=self.department, level=300, semester="first", lecturer=self.other_lecturer,
        )

        self.client.login(username="lect1", password="pass12345")

    def test_lists_only_own_courses(self):
        response = self.client.get(reverse("courses:my_courses"))
        self.assertContains(response, "CSC301")
        self.assertNotContains(response, "CSC303")

    def test_non_lecturer_gets_403(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("courses:my_courses"))
        self.assertEqual(response.status_code, 403)

    def test_only_shows_current_semester_courses(self):
        # settings.CURRENT_SEMESTER is "first" - a course sitting in the semester
        # that hasn't started yet shouldn't show up in the day-to-day course list at all.
        Course.objects.create(
            code="CSC302", title="Not Yet", units=3,
            department=self.department, level=300, semester="second", lecturer=self.lecturer,
        )
        response = self.client.get(reverse("courses:my_courses"))
        self.assertContains(response, "CSC301")
        self.assertNotContains(response, "CSC302")
