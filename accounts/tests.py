from django.conf import settings
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from students.models import Department, StudentProfile
from students.services import create_student_account

from .models import ADMIN_GROUP, BURSAR_GROUP, DEAN_GROUP, HOD_GROUP, LECTURER_GROUP, REGISTRAR_GROUP, User
from .services import assign_staff_identity


def make_admin():
    admin = User.objects.create_user(username="admin", email="admin@example.com", password="pass12345")
    admin.groups.add(Group.objects.get(name=ADMIN_GROUP))
    return admin


def make_hod(username="hod1"):
    hod = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    hod.groups.add(Group.objects.get(name=HOD_GROUP))
    return hod


def make_lecturer(username="lect1"):
    lecturer = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    lecturer.groups.add(Group.objects.get(name=LECTURER_GROUP))
    return lecturer


def make_registrar(username="reg1"):
    registrar = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    registrar.groups.add(Group.objects.get(name=REGISTRAR_GROUP))
    return registrar


def make_bursar(username="bursar1"):
    bursar = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    bursar.groups.add(Group.objects.get(name=BURSAR_GROUP))
    return bursar


def make_dean(username="dean1"):
    dean = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    dean.groups.add(Group.objects.get(name=DEAN_GROUP))
    return dean


class LoginTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile, self.pin = create_student_account(
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
        self.profile, self.pin = create_student_account(
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
                "pin": self.pin,
            },
        )
        self.profile.user.refresh_from_db()
        self.assertFalse(self.profile.user.must_change_password)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("student_dashboard"))

    def test_weak_password_rejected(self):
        # all-lowercase, no digit or symbol - fails ComplexityValidator even though
        # it clears the length requirement on its own.
        response = self.client.post(
            reverse("accounts:change_password"),
            {"new_password1": "weakpassword", "new_password2": "weakpassword", "pin": self.pin},
        )
        self.profile.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.profile.user.must_change_password)


class AdminOnlyViewsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.admin_user = make_admin()

        self.student_profile, _ = create_student_account(
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
        for name in [
            "accounts:register",
            "students:bulk_import",
            "students:lookup",
            "accounts:manage_staff",
            "accounts:staff_add",
        ]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

        staff = make_hod(username="hod_for_forbidden_test")
        self.assertEqual(
            self.client.get(reverse("accounts:staff_edit", args=[staff.id])).status_code, 403
        )

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
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("PIN", mail.outbox[0].subject)

    def test_admin_can_add_staff(self):
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_add"),
            {
                "first_name": "New",
                "last_name": "Lecturer",
                "email": "newlect@example.com",
                "staff_id": "2026/CSC/010",
                "group": Group.objects.get(name=LECTURER_GROUP).id,
            },
        )
        self.assertRedirects(response, reverse("accounts:manage_staff"))
        new_staff = User.objects.get(email="newlect@example.com")
        self.assertEqual(new_staff.staff_id, "2026/CSC/010")
        self.assertEqual(new_staff.username, "2026csc010")
        self.assertTrue(new_staff.groups.filter(name=LECTURER_GROUP).exists())

    def test_admin_cannot_add_staff_with_duplicate_id(self):
        self.client.login(username="admin", password="pass12345")
        User.objects.create_user(
            username="existinghod", email="existinghod@example.com", password="pass12345",
            staff_id="2026/CSC/001",
        )
        response = self.client.post(
            reverse("accounts:staff_add"),
            {
                "first_name": "Another",
                "last_name": "Lecturer",
                "email": "another@example.com",
                "staff_id": "2026/csc/001",
                "group": Group.objects.get(name=LECTURER_GROUP).id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="another@example.com").exists())
        self.assertContains(response, "already exists")

    def test_admin_can_edit_staff(self):
        staff = make_hod(username="hodtoedit")
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_edit", args=[staff.id]),
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": staff.email,
                "is_active": "on",
                "group": Group.objects.get(name=LECTURER_GROUP).id,
            },
        )
        self.assertRedirects(response, reverse("accounts:manage_staff"))
        staff.refresh_from_db()
        self.assertEqual(staff.first_name, "Updated")
        self.assertTrue(staff.groups.filter(name=LECTURER_GROUP).exists())
        self.assertFalse(staff.groups.filter(name=HOD_GROUP).exists())

    def test_editing_staff_does_not_flag_own_unchanged_email(self):
        staff = make_hod(username="hodkeepemail")
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_edit", args=[staff.id]),
            {
                "first_name": staff.first_name,
                "last_name": staff.last_name,
                "email": staff.email,
                "is_active": "on",
                "group": Group.objects.get(name=HOD_GROUP).id,
            },
        )
        self.assertRedirects(response, reverse("accounts:manage_staff"))

    def test_deactivated_staff_cannot_log_in(self):
        staff = make_hod(username="hodtodeactivate")
        self.client.login(username="admin", password="pass12345")
        self.client.post(
            reverse("accounts:staff_edit", args=[staff.id]),
            {
                "first_name": staff.first_name,
                "last_name": staff.last_name,
                "email": staff.email,
                "group": Group.objects.get(name=HOD_GROUP).id,
                # is_active omitted - unchecked checkbox
            },
        )
        self.client.logout()
        self.assertFalse(self.client.login(username="hodtodeactivate", password="pass12345"))


class ManageStaffFilterTests(TestCase):
    def setUp(self):
        self.admin_user = make_admin()
        self.hod = make_hod(username="hodforfilter")
        self.lecturer = make_lecturer(username="lectforfilter")
        self.lecturer.is_active = False
        self.lecturer.save(update_fields=["is_active"])
        self.client.login(username="admin", password="pass12345")

    def test_filter_by_role(self):
        response = self.client.get(reverse("accounts:manage_staff"), {"group": Group.objects.get(name=HOD_GROUP).id})
        self.assertContains(response, "hodforfilter")
        self.assertNotContains(response, "lectforfilter")

    def test_filter_by_active_status(self):
        response = self.client.get(reverse("accounts:manage_staff"), {"is_active": "0"})
        self.assertContains(response, "lectforfilter")
        self.assertNotContains(response, "hodforfilter")

    def test_pagination_limits_to_ten_per_page(self):
        for i in range(15):
            make_hod(username=f"pagstaff{i}")
        response = self.client.get(reverse("accounts:manage_staff"))
        self.assertEqual(len(response.context["staff_users"]), 10)

        response_page2 = self.client.get(reverse("accounts:manage_staff"), {"page": 2})
        self.assertEqual(response_page2.context["staff_users"].number, 2)


class StaffIdentityTests(TestCase):
    """Covers accounts.services.assign_staff_identity() directly - the admin add_view
    wiring around it is exercised separately in AdminStaffCreationTests."""

    def test_username_derived_from_staff_id(self):
        user = assign_staff_identity(
            User(email="a@example.com", first_name="A", last_name="One", staff_id="2026/CSC/003")
        )
        user.save()

        self.assertEqual(user.staff_id, "2026/CSC/003")
        self.assertEqual(user.username, "2026csc003")

    def test_default_password_and_forced_change(self):
        user = assign_staff_identity(
            User(email="c@example.com", first_name="C", last_name="Three", staff_id="2026/CSC/004")
        )
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
                "staff_id": "2026/CSC/020",
                "groups": [Group.objects.get(name=LECTURER_GROUP).id],
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="grace@example.com")
        self.assertEqual(user.staff_id, "2026/CSC/020")
        self.assertEqual(user.username, "2026csc020")
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.groups.filter(name=LECTURER_GROUP).exists())


class DashboardRoutingTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.student_profile, _ = create_student_account(
            matric_number="2023/CSC/050",
            first_name="Sam",
            last_name="Okoro",
            email="sam@example.com",
            department=self.department,
            entry_level=200,
        )
        # Skip the forced-password-change redirect - covered separately in
        # ForcedPasswordChangeTests.
        self.student_profile.user.must_change_password = False
        self.student_profile.user.save(update_fields=["must_change_password"])

    def test_admin_redirected_to_admin_dashboard(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("admin_dashboard"))

    def test_hod_redirected_to_hod_dashboard(self):
        make_hod()
        self.client.login(username="hod1", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("hod_dashboard"))

    def test_lecturer_redirected_to_lecturer_dashboard(self):
        make_lecturer()
        self.client.login(username="lect1", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("lecturer_dashboard"))

    def test_student_redirected_to_student_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("student_dashboard"))

    def test_hod_takes_priority_over_lecturer(self):
        # A department head is usually also a Lecturer - HOD should win.
        user = make_hod(username="hodlect")
        user.groups.add(Group.objects.get(name=LECTURER_GROUP))
        self.client.login(username="hodlect", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("hod_dashboard"))

    def test_registrar_redirected_to_registrar_dashboard(self):
        make_registrar()
        self.client.login(username="reg1", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("registrar_dashboard"))

    def test_bursar_redirected_to_bursar_dashboard(self):
        make_bursar()
        self.client.login(username="bursar1", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("bursar_dashboard"))

    def test_dean_redirected_to_dean_dashboard(self):
        make_dean()
        self.client.login(username="dean1", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("dean_dashboard"))

    def test_dean_takes_priority_over_hod(self):
        # A Dean is senior academic staff, often also an HOD in a smaller faculty -
        # Dean should win.
        user = make_dean(username="deanhod")
        user.groups.add(Group.objects.get(name=HOD_GROUP))
        self.client.login(username="deanhod", password="pass12345")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("dean_dashboard"))

    def test_non_registrar_forbidden_from_registrar_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse("registrar_dashboard")).status_code, 403)

    def test_non_bursar_forbidden_from_bursar_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse("bursar_dashboard")).status_code, 403)

    def test_non_dean_forbidden_from_dean_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse("dean_dashboard")).status_code, 403)

    def test_non_admin_forbidden_from_admin_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 403)

    def test_non_hod_forbidden_from_hod_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse("hod_dashboard")).status_code, 403)

    def test_non_lecturer_forbidden_from_lecturer_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        self.assertEqual(self.client.get(reverse("lecturer_dashboard")).status_code, 403)

    def test_non_student_forbidden_from_student_dashboard(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        self.assertEqual(self.client.get(reverse("student_dashboard")).status_code, 403)


class PinVerificationTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile, self.pin = create_student_account(
            matric_number="2023/CSC/060",
            first_name="Ngozi",
            last_name="Eze",
            email="ngozi@example.com",
            department=self.department,
            entry_level=200,
        )
        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)

    def _change_password(self, pin):
        return self.client.post(
            reverse("accounts:change_password"),
            {"new_password1": "N3wPassw0rd!", "new_password2": "N3wPassw0rd!", "pin": pin},
        )

    def test_correct_pin_allows_password_change(self):
        self._change_password(self.pin)
        self.profile.user.refresh_from_db()
        self.assertFalse(self.profile.user.must_change_password)
        self.assertTrue(self.profile.user.check_password("N3wPassw0rd!"))

    def test_wrong_pin_rejected(self):
        response = self._change_password("000000")
        self.profile.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.profile.user.must_change_password)
        self.assertFalse(self.profile.user.check_password("N3wPassw0rd!"))

    def test_lockout_after_max_attempts(self):
        for _ in range(settings.PIN_MAX_ATTEMPTS):
            self._change_password("000000")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_pin_locked)

        # Even the correct PIN is rejected once locked.
        response = self._change_password(self.pin)
        self.assertContains(response, "Too many wrong PIN attempts")
        self.profile.user.refresh_from_db()
        self.assertTrue(self.profile.user.must_change_password)

    def test_staff_forced_password_change_has_no_pin_field(self):
        staff = make_admin()
        staff.must_change_password = True
        staff.save(update_fields=["must_change_password"])
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("accounts:change_password"))
        self.assertNotContains(response, 'name="pin"')

        response = self.client.post(
            reverse("accounts:change_password"),
            {"new_password1": "N3wPassw0rd!", "new_password2": "N3wPassw0rd!"},
        )
        staff.refresh_from_db()
        self.assertFalse(staff.must_change_password)
