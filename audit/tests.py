from datetime import timedelta

from accounts.models import ADMIN_GROUP, DEAN_GROUP, HOD_GROUP, LECTURER_GROUP, STUDENT_GROUP, User
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseRegistration
from students.models import Department, Faculty
from students.services import create_student_account

from .models import AuditLog, AuditLogImmutableError
from .services import log_action


def make_admin(username="admin1"):
    admin = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    admin.groups.add(Group.objects.get(name=ADMIN_GROUP))
    return admin


def make_hod(username="hod1", department=None):
    hod = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    hod.groups.add(Group.objects.get(name=HOD_GROUP))
    if department is not None:
        department.hod = hod
        department.save(update_fields=["hod"])
    return hod


def make_lecturer(username="lect1"):
    lecturer = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    lecturer.groups.add(Group.objects.get(name=LECTURER_GROUP))
    return lecturer


def make_dean(username="dean1", faculty=None):
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
    # Real password required for tests that log in via a normal (non-first-login)
    # session - see accounts.models.User.skips_first_login_password.
    profile.user.set_password("pass12345")
    profile.user.must_change_password = False
    profile.user.save(update_fields=["password", "must_change_password"])
    return profile


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


class AuditLogImmutabilityTests(TestCase):
    """FR-LOG-05: no role, including code, can edit or delete a log entry."""

    def test_creating_new_entry_succeeds(self):
        log_action(action=AuditLog.CREATE, target_description="Faculty of Science")
        entry = AuditLog.objects.get()
        self.assertEqual(entry.action, AuditLog.CREATE)
        self.assertIsNotNone(entry.created_at)

    def test_cannot_resave_existing_entry(self):
        log_action(action=AuditLog.CREATE, target_description="Faculty of Science")
        entry = AuditLog.objects.get()
        entry.reason = "tampered"
        with self.assertRaises(AuditLogImmutableError):
            entry.save()

    def test_cannot_delete_entry(self):
        log_action(action=AuditLog.CREATE, target_description="Faculty of Science")
        entry = AuditLog.objects.get()
        with self.assertRaises(AuditLogImmutableError):
            entry.delete()

    def test_queryset_update_is_blocked(self):
        log_action(action=AuditLog.CREATE, target_description="Faculty of Science")
        with self.assertRaises(AuditLogImmutableError):
            AuditLog.objects.all().update(reason="tampered")

    def test_queryset_delete_is_blocked(self):
        log_action(action=AuditLog.CREATE, target_description="Faculty of Science")
        with self.assertRaises(AuditLogImmutableError):
            AuditLog.objects.all().delete()


class LoginLoggingTests(TestCase):
    """FR-LOG-01: every login attempt, successful or failed, logged with a timestamp.

    Drives the real login view/form so LenientUsernameBackend runs for real -
    not calling the backend directly - so this also proves the request actually
    reaches the logging call sites added in accounts/auth_backends.py.
    """

    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")

    def test_unknown_username_logs_login_failed(self):
        self.client.post(reverse("login"), {"username": "totally-unknown", "password": "whatever"})
        entry = AuditLog.objects.get(action=AuditLog.LOGIN_FAILED)
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_username, "totally-unknown")
        self.assertIn("unknown username", entry.reason)
        self.assertIsNotNone(entry.created_at)

    def test_ambiguous_username_logs_login_failed(self):
        # One user's real username collides with a different user's chosen
        # preferred_username - LenientUsernameBackend's OR query matches both.
        User.objects.create_user(username="abcd", email="a@example.com", password="pass12345")
        other = User.objects.create_user(username="somethingelse", email="b@example.com", password="pass12345")
        other.preferred_username = "abcd"
        other.save(update_fields=["preferred_username"])

        self.client.post(reverse("login"), {"username": "abcd", "password": "whatever"})
        entry = AuditLog.objects.get(action=AuditLog.LOGIN_FAILED)
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_username, "abcd")
        self.assertIn("ambiguous", entry.reason)

    def test_locked_out_account_logs_login_failed(self):
        user = make_lecturer("locktest")
        user.failed_login_attempts = 5
        user.login_locked_until = timezone.now() + timedelta(minutes=15)
        user.save(update_fields=["failed_login_attempts", "login_locked_until"])

        self.client.post(reverse("login"), {"username": "locktest", "password": "pass12345"})
        entry = AuditLog.objects.get(action=AuditLog.LOGIN_FAILED)
        self.assertEqual(entry.actor, user)
        self.assertIn("locked", entry.reason)

    def test_wrong_password_logs_login_failed(self):
        make_lecturer("wrongpwtest")
        self.client.post(reverse("login"), {"username": "wrongpwtest", "password": "not-the-password"})
        entry = AuditLog.objects.get(action=AuditLog.LOGIN_FAILED)
        self.assertEqual(entry.actor_username, "wrongpwtest")
        self.assertIn("incorrect password", entry.reason)

    def test_correct_password_logs_login_success(self):
        user = make_lecturer("correctpwtest")
        self.client.post(reverse("login"), {"username": "correctpwtest", "password": "pass12345"})
        entry = AuditLog.objects.get(action=AuditLog.LOGIN_SUCCESS)
        self.assertEqual(entry.actor, user)

    def test_first_login_passwordless_student_logs_login_success(self):
        profile = create_student_account(
            matric_number="2025/CSC/001", first_name="New", last_name="Student",
            email="newstudent@example.com", department=self.department, entry_level=100,
        )
        self.client.post(reverse("login"), {"username": profile.user.username, "password": ""})
        entry = AuditLog.objects.get(action=AuditLog.LOGIN_SUCCESS)
        self.assertEqual(entry.actor, profile.user)
        self.assertIn("passwordless", entry.reason)

    def test_inactive_account_correct_password_logs_login_failed(self):
        user = make_lecturer("inactivetest")
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.client.post(reverse("login"), {"username": "inactivetest", "password": "pass12345"})
        entry = AuditLog.objects.get(action=AuditLog.LOGIN_FAILED)
        self.assertEqual(entry.actor, user)
        self.assertIn("inactive", entry.reason)


class AccessDeniedLoggingTests(TestCase):
    """FR-LOG-03: every denied access attempt, with user/route/reason. Covered by a
    single middleware hook (audit/middleware.py) rather than edits to each of the
    9 `raise PermissionDenied(...)` sites project-wide - these tests exercise several
    of those sites to prove the shared hook actually catches all of them.
    """

    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")

    def test_authenticated_wrong_role_logs_access_denied(self):
        student = make_student("2023/CSC/050", self.department, 300)
        self.client.login(username=student.user.username, password="pass12345")
        url = reverse("accounts:manage_staff")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)
        entry = AuditLog.objects.get(action=AuditLog.ACCESS_DENIED)
        self.assertEqual(entry.actor, student.user)
        self.assertEqual(entry.request_path, url)
        self.assertIn("admins", entry.reason)

    def test_anonymous_hit_does_not_log_access_denied(self):
        response = self.client.get(reverse("accounts:manage_staff"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.ACCESS_DENIED).count(), 0)

    def test_second_decorator_also_logged(self):
        # Proves the shared middleware hook fires for more than one decorator, not
        # just admin_required - not testing all 7 near-duplicate branches.
        student = make_student("2023/CSC/051", self.department, 300)
        self.client.login(username=student.user.username, password="pass12345")

        response = self.client.get(reverse("courses:manage_courses"))

        self.assertEqual(response.status_code, 403)
        entry = AuditLog.objects.get(action=AuditLog.ACCESS_DENIED)
        self.assertEqual(entry.actor, student.user)
        self.assertIn("hods", entry.reason.lower())

    def test_dashboard_unassigned_role_denial_logged(self):
        # A user in no role group at all - accounts/views.py's ad hoc raise site,
        # not one of the 7 decorators.
        orphan = User.objects.create_user(username="orphan", email="orphan@example.com", password="pass12345")
        self.client.login(username="orphan", password="pass12345")

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 403)
        entry = AuditLog.objects.get(action=AuditLog.ACCESS_DENIED)
        self.assertEqual(entry.actor, orphan)
        self.assertIn("isn't assigned to a role", entry.reason)

    def test_results_entry_unauthorized_denial_logged(self):
        lecturer = make_lecturer("nonowning")
        other_lecturer = make_lecturer("owning")
        course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first", lecturer=other_lecturer,
        )
        self.client.login(username="nonowning", password="pass12345")

        response = self.client.get(reverse("results:course_results_entry", args=[course.id]))

        self.assertEqual(response.status_code, 403)
        entry = AuditLog.objects.get(action=AuditLog.ACCESS_DENIED)
        self.assertEqual(entry.actor, lecturer)
        self.assertIn("not authorized", entry.reason)


class AcademicRecordCreateUpdateLoggingTests(TestCase):
    """FR-LOG-02 (academic half - no financial records/models exist yet, and no
    hard-delete code path exists anywhere in this codebase to log a DELETE from)."""

    def setUp(self):
        self.department = Department.objects.create(name="Computer Science", duration_years=4)

    def test_register_view_logs_create(self):
        registrar = User.objects.create_user(username="reg1", email="reg1@example.com", password="pass12345")
        registrar.groups.add(Group.objects.get(name="Registrar"))
        self.client.login(username="reg1", password="pass12345")

        self.client.post(reverse("students:register"), {
            "first_name": "New", "last_name": "Student", "email": "newstu@example.com",
            "matric_number": "2025/CSC/200", "department": self.department.id,
            "level": 100, "admission_type": "UTME",
        })

        entry = AuditLog.objects.get(action=AuditLog.CREATE)
        self.assertEqual(entry.actor, registrar)
        self.assertIn("2025/CSC/200", entry.target_description)

    def test_bulk_import_logs_create_per_row(self):
        registrar = User.objects.create_user(username="reg2", email="reg2@example.com", password="pass12345")
        registrar.groups.add(Group.objects.get(name="Registrar"))
        self.client.login(username="reg2", password="pass12345")

        csv_content = (
            "matric_number,first_name,last_name,email,department,level,admission_type\n"
            "2025/CSC/201,John,Doe,john@example.com,Computer Science,100,UTME\n"
            "2025/CSC/202,Jane,Roe,jane@example.com,Computer Science,100,UTME\n"
        )
        upload = SimpleUploadedFile("students.csv", csv_content.encode("utf-8"), content_type="text/csv")
        self.client.post(reverse("students:bulk_import"), {"csv_file": upload})

        self.assertEqual(AuditLog.objects.filter(action=AuditLog.CREATE).count(), 2)

    def test_faculty_add_logs_create(self):
        make_admin()
        self.client.login(username="admin1", password="pass12345")

        self.client.post(reverse("students:faculty_add"), {"name": "Faculty of Science", "dean": ""})

        entry = AuditLog.objects.get(action=AuditLog.CREATE)
        self.assertIn("Faculty of Science", entry.target_description)

    def test_faculty_edit_logs_update(self):
        make_admin()
        self.client.login(username="admin1", password="pass12345")
        faculty = Faculty.objects.create(name="Faculty of Science")

        self.client.post(
            reverse("students:faculty_edit", args=[faculty.id]),
            {"name": "Faculty of Pure Science", "dean": ""},
        )

        entry = AuditLog.objects.get(action=AuditLog.UPDATE)
        self.assertIn("Faculty of Pure Science", entry.target_description)

    def test_department_add_logs_create(self):
        make_admin()
        self.client.login(username="admin1", password="pass12345")

        self.client.post(reverse("students:department_add"), {
            "name": "Physics", "duration_years": 4, "faculty": "", "hod": "",
        })

        entry = AuditLog.objects.get(action=AuditLog.CREATE)
        self.assertIn("Physics", entry.target_description)

    def test_department_edit_logs_update(self):
        make_admin()
        self.client.login(username="admin1", password="pass12345")
        department = Department.objects.create(name="Physics", duration_years=4)

        self.client.post(
            reverse("students:department_edit", args=[department.id]),
            {"name": "Applied Physics", "duration_years": 4, "faculty": "", "hod": ""},
        )

        entry = AuditLog.objects.get(action=AuditLog.UPDATE)
        self.assertIn("Applied Physics", entry.target_description)

    def test_course_add_logs_create(self):
        hod = make_hod(department=self.department)
        self.client.login(username="hod1", password="pass12345")

        self.client.post(reverse("courses:course_add"), {
            "code": "csc301", "title": "Algorithms", "units": 3,
            "level": 300, "semester": "first", "lecturer": "", "is_active": "on",
        })

        entry = AuditLog.objects.get(action=AuditLog.CREATE)
        self.assertEqual(entry.actor, hod)
        self.assertIn("CSC301", entry.target_description)

    def test_course_edit_logs_update(self):
        hod = make_hod(department=self.department)
        self.client.login(username="hod1", password="pass12345")
        course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first",
        )

        self.client.post(reverse("courses:course_edit", args=[course.id]), {
            "code": "csc301", "title": "Algorithms II", "units": 3,
            "level": 300, "semester": "first", "lecturer": "", "is_active": "on",
        })

        entry = AuditLog.objects.get(action=AuditLog.UPDATE)
        self.assertEqual(entry.actor, hod)

    def test_course_toggle_active_logs_update(self):
        hod = make_hod(department=self.department)
        self.client.login(username="hod1", password="pass12345")
        course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first",
        )

        self.client.post(reverse("courses:course_toggle_active", args=[course.id]))

        entry = AuditLog.objects.get(action=AuditLog.UPDATE)
        self.assertEqual(entry.actor, hod)
        self.assertIn("is_active", entry.reason)

    def test_course_registration_logs_create_per_course(self):
        student = make_student("2023/CSC/060", self.department, 300)
        course_a = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first",
        )
        course_b = Course.objects.create(
            code="CSC303", title="Databases", units=3,
            department=self.department, level=300, semester="first",
        )
        self.client.login(username=student.user.username, password="pass12345")

        self.client.post(reverse("courses:register"), {"courses": [course_a.id, course_b.id]})

        # AuditLog.CREATE also includes the make_student() setup call above (a
        # StudentProfile create) - filter to just the registrations this test cares about.
        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.CREATE, target_description__contains="CourseRegistration").count(),
            2,
        )

    def test_result_entry_logs_create_then_update(self):
        lecturer = make_lecturer("resultlect")
        hod = make_hod("resulthod", department=self.department)
        student = make_student("2023/CSC/070", self.department, 300)
        course = Course.objects.create(
            code="CSC301", title="Algorithms", units=3,
            department=self.department, level=300, semester="first", lecturer=lecturer,
        )
        registration = CourseRegistration.objects.create(
            student=student, course=course, session="2025/2026", semester="first",
        )
        url = reverse("results:course_results_entry", args=[course.id])

        self.client.login(username="resultlect", password="pass12345")
        self.client.post(f"{url}?session=2025/2026", _formset_post_data([(registration.id, 75)]))
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.CREATE, target_description__contains="Result").count(), 1)

        self.client.login(username="resulthod", password="pass12345")
        self.client.post(f"{url}?session=2025/2026", _formset_post_data([(registration.id, 80)]))
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.UPDATE, target_description__contains="Result").count(), 1)


class AuditLogViewAccessTests(TestCase):
    """FR-LOG-04: audit logs viewable only by IT Admin/Super Admin."""

    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("audit:log_list"))
        self.assertEqual(response.status_code, 302)

    def test_non_admin_gets_403(self):
        student = make_student("2023/CSC/080", self.department, 300)
        self.client.login(username=student.user.username, password="pass12345")
        self.assertEqual(self.client.get(reverse("audit:log_list")).status_code, 403)

        make_lecturer("viewlect")
        self.client.login(username="viewlect", password="pass12345")
        self.assertEqual(self.client.get(reverse("audit:log_list")).status_code, 403)

    def test_admin_can_view_log_list(self):
        make_admin()
        log_action(action=AuditLog.CREATE, target_description="Faculty of Science")
        self.client.login(username="admin1", password="pass12345")

        response = self.client.get(reverse("audit:log_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Faculty of Science")

    def test_list_shows_most_recent_first(self):
        make_admin()
        # client.login() itself produces a LOGIN_SUCCESS entry - log in first so
        # these two are unambiguously the most recent when the page is fetched.
        self.client.login(username="admin1", password="pass12345")
        log_action(action=AuditLog.CREATE, target_description="First entry")
        log_action(action=AuditLog.CREATE, target_description="Second entry")

        response = self.client.get(reverse("audit:log_list"))

        logs = list(response.context["logs"])
        self.assertEqual(logs[0].target_description, "Second entry")
        self.assertEqual(logs[1].target_description, "First entry")

    def test_action_filter_narrows_results(self):
        make_admin()
        log_action(action=AuditLog.CREATE, target_description="A create")
        log_action(action=AuditLog.LOGIN_SUCCESS, actor_username="admin1")
        self.client.login(username="admin1", password="pass12345")

        response = self.client.get(reverse("audit:log_list"), {"action": AuditLog.CREATE})

        logs = list(response.context["logs"])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, AuditLog.CREATE)
