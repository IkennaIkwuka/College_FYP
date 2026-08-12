from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from students.models import AdmissionRecord, Department, StudentProfile
from students.services import create_student_account, seed_admission_record

from .models import ADMIN_GROUP, LECTURER_GROUP, User
from .services import assign_staff_identity


def make_admin():
    admin = User.objects.create_user(username="admin", email="admin@example.com", password="pass12345")
    admin.groups.add(Group.objects.get(name=ADMIN_GROUP))
    return admin


class LoginTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = create_student_account(
            matric_number="2023/CSC/030",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            department=self.department,
            entry_level=300,
        )

    def test_login_with_username_still_works(self):
        self.assertTrue(
            self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)
        )

    def test_login_with_matric_number_no_longer_works(self):
        # The matric-number login fallback was removed - login is username+password only.
        self.assertFalse(
            self.client.login(username="2023/CSC/030", password=settings.DEFAULT_PASSWORD)
        )


class ForcedPasswordChangeTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = create_student_account(
            matric_number="2023/CSC/031",
            first_name="John",
            last_name="Smith",
            email="john@example.com",
            department=self.department,
            entry_level=300,
        )
        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)

    def test_redirected_to_change_password(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("accounts:change_password"))

    def test_flag_clears_after_change(self):
        # No old_password field - first-time change deliberately doesn't ask for it.
        self.client.post(
            reverse("accounts:change_password"),
            {
                "new_password1": "N3wPassw0rd!",
                "new_password2": "N3wPassw0rd!",
            },
        )
        self.profile.user.refresh_from_db()
        self.assertFalse(self.profile.user.must_change_password)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_weak_password_rejected(self):
        # all-lowercase, no digit or symbol - fails ComplexityValidator even though
        # it clears the length requirement on its own.
        response = self.client.post(
            reverse("accounts:change_password"),
            {"new_password1": "weakpassword", "new_password2": "weakpassword"},
        )
        self.profile.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.profile.user.must_change_password)


class AdminOnlyViewsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.admin_user = make_admin()

        self.student_profile = create_student_account(
            matric_number="2023/CSC/032",
            first_name="Ann",
            last_name="Lee",
            email="ann@example.com",
            department=self.department,
            entry_level=200,
        )
        # Skip the forced-password-change redirect for these permission checks -
        # that flow is covered separately in ForcedPasswordChangeTests.
        self.student_profile.user.must_change_password = False
        self.student_profile.user.save(update_fields=["must_change_password"])

    def test_non_admin_forbidden(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        for name in ["accounts:register", "students:bulk_import", "students:lookup", "students:seed_admissions"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_admin_can_add_student(self):
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "new@example.com",
                "matric_number": "2023/CSC/099",
                "department": self.department.id,
                "level": 100,
            },
        )
        self.assertRedirects(response, reverse("accounts:register"))
        self.assertTrue(StudentProfile.objects.filter(matric_number="2023/CSC/099").exists())


class StaffIdentityTests(TestCase):
    """Covers accounts.services.assign_staff_identity() directly - the admin add_view
    wiring around it is exercised separately in AdminStaffCreationTests."""

    def test_sequential_ids_and_lowercase_username(self):
        user1 = assign_staff_identity(User(email="a@example.com", first_name="A", last_name="One"))
        user1.save()
        user2 = assign_staff_identity(User(email="b@example.com", first_name="B", last_name="Two"))
        user2.save()

        self.assertEqual(user1.staff_id, "STF0001")
        self.assertEqual(user1.username, "stf0001")
        self.assertEqual(user2.staff_id, "STF0002")

    def test_default_password_and_forced_change(self):
        user = assign_staff_identity(User(email="c@example.com", first_name="C", last_name="Three"))
        user.save()
        self.assertTrue(user.check_password(settings.DEFAULT_PASSWORD))
        self.assertTrue(user.must_change_password)


class AdminStaffCreationTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="root", email="root@example.com", password="pass12345"
        )
        self.client.login(username="root", password="pass12345")

    def test_creating_staff_via_admin_generates_identity(self):
        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace@example.com",
                "groups": [Group.objects.get(name=LECTURER_GROUP).id],
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="grace@example.com")
        self.assertEqual(user.staff_id, "STF0001")
        self.assertEqual(user.username, "stf0001")
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.groups.filter(name=LECTURER_GROUP).exists())


class SelfRegistrationTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.record, self.pin = seed_admission_record(
            matric_number="2024/CSC/010",
            first_name="Kelechi",
            last_name="Nwosu",
            email="kelechi@example.com",
            department=self.department,
            entry_level=100,
        )

    def _start(self):
        return self.client.post(reverse("accounts:self_register_start"), {"matric_number": "2024/CSC/010"})

    def test_full_happy_path_creates_account(self):
        self._start()
        self.client.post(reverse("accounts:self_register_pin"), {"pin": self.pin})
        response = self.client.post(
            reverse("accounts:self_register_password"),
            {"password1": "Str0ng!Passw0rd", "password2": "Str0ng!Passw0rd"},
        )
        self.assertRedirects(response, reverse("login"))
        self.assertFalse(AdmissionRecord.objects.filter(id=self.record.id).exists())

        profile = StudentProfile.objects.get(matric_number="2024/CSC/010")
        self.assertFalse(profile.user.must_change_password)
        self.assertTrue(profile.user.check_password("Str0ng!Passw0rd"))
        self.assertTrue(self.client.login(username=profile.user.username, password="Str0ng!Passw0rd"))

    def test_unknown_matric_number_generic_error(self):
        response = self.client.post(
            reverse("accounts:self_register_start"), {"matric_number": "9999/XX/999"}
        )
        self.assertContains(response, "find an admission record")

    def test_pin_lockout_after_max_attempts(self):
        self._start()
        for _ in range(settings.PIN_MAX_ATTEMPTS):
            self.client.post(reverse("accounts:self_register_pin"), {"pin": "000000"})
        self.record.refresh_from_db()
        self.assertTrue(self.record.is_locked)

        # A fresh attempt (right or wrong) now bounces back to step 1 with a lockout message.
        response = self.client.post(reverse("accounts:self_register_pin"), {"pin": self.pin}, follow=True)
        self.assertRedirects(response, reverse("accounts:self_register_start"))

    def test_cannot_skip_to_password_step(self):
        # No prior matric/PIN steps in this session.
        response = self.client.get(reverse("accounts:self_register_password"))
        self.assertRedirects(response, reverse("accounts:self_register_start"))

    def test_cannot_reach_password_step_without_pin_verification(self):
        self._start()
        response = self.client.get(reverse("accounts:self_register_password"))
        self.assertRedirects(response, reverse("accounts:self_register_start"))
