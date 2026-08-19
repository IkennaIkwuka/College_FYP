import re

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

    def test_login_with_matric_number_in_natural_form_works(self):
        # LenientUsernameBackend strips punctuation and ignores case, so typing the
        # matric number in its natural shape (slashes, mixed case) still logs in -
        # it isn't a separate lookup path, just tolerance on the same username field.
        self.assertTrue(
            self.client.login(username="2023/csc/030", password=settings.DEFAULT_PASSWORD)
        )

    def test_login_with_unrelated_wrong_username_fails(self):
        self.assertFalse(
            self.client.login(username="not-a-real-account", password=settings.DEFAULT_PASSWORD)
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
        # No PIN is issued at creation anymore - set one directly, as if the student
        # had already gone through "Send code" themselves.
        self.profile.set_pin("123456")
        self.profile.save(update_fields=["pin_hash"])
        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)

    def _verify_pin(self):
        return self.client.post(reverse("accounts:verify_pin"), {"pin": "123456"})

    def test_redirected_to_verify_pin(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("accounts:verify_pin"))

    def test_flag_clears_after_change(self):
        self._verify_pin()
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
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("student_dashboard"))

    def test_weak_password_rejected(self):
        self._verify_pin()
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
        for name in [
            "students:lookup",
            "accounts:manage_staff",
            "accounts:staff_add",
        ]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

        staff = make_hod(username="hod_for_forbidden_test")
        self.assertEqual(
            self.client.get(reverse("accounts:staff_edit", args=[staff.id])).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("accounts:staff_force_password_reset", args=[staff.id])
            ).status_code,
            403,
        )

    def test_admin_forbidden_from_add_student(self):
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
                "admission_type": "UTME",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(StudentProfile.objects.filter(matric_number="2023/CSC/099").exists())

    def test_registrar_can_add_student(self):
        make_registrar()
        self.client.login(username="reg1", password="pass12345")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "new@example.com",
                "matric_number": "2023/CSC/099",
                "department": self.department.id,
                "level": 100,
                "admission_type": "UTME",
            },
        )
        self.assertRedirects(response, reverse("accounts:register"))
        self.assertTrue(StudentProfile.objects.filter(matric_number="2023/CSC/099").exists())
        # No PIN is issued at creation anymore - the student requests one themselves
        # at first login (accounts:send_pin_code).
        self.assertEqual(len(mail.outbox), 0)

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

    def test_admin_can_add_registrar_when_none_active(self):
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_add"),
            {
                "first_name": "First",
                "last_name": "Registrar",
                "email": "firstreg@example.com",
                "staff_id": "2026/REG/001",
                "group": Group.objects.get(name=REGISTRAR_GROUP).id,
            },
        )
        self.assertRedirects(response, reverse("accounts:manage_staff"))
        self.assertTrue(User.objects.filter(email="firstreg@example.com").exists())

    def test_admin_cannot_add_second_active_registrar(self):
        make_registrar()
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_add"),
            {
                "first_name": "Second",
                "last_name": "Registrar",
                "email": "secondreg@example.com",
                "staff_id": "2026/REG/002",
                "group": Group.objects.get(name=REGISTRAR_GROUP).id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="secondreg@example.com").exists())
        self.assertContains(response, "already an active Registrar")

    def test_admin_cannot_add_second_active_bursar(self):
        make_bursar()
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_add"),
            {
                "first_name": "Second",
                "last_name": "Bursar",
                "email": "secondbursar@example.com",
                "staff_id": "2026/BUR/002",
                "group": Group.objects.get(name=BURSAR_GROUP).id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="secondbursar@example.com").exists())
        self.assertContains(response, "already an active Bursar")

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

    def test_admin_can_force_staff_password_reset(self):
        staff = make_hod(username="hodtoreset")
        staff.set_password("someoldpassword")
        staff.must_change_password = False
        staff.save()
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(reverse("accounts:staff_force_password_reset", args=[staff.id]))
        self.assertRedirects(response, reverse("accounts:manage_staff"))
        staff.refresh_from_db()
        self.assertTrue(staff.check_password(settings.DEFAULT_PASSWORD))
        self.assertTrue(staff.must_change_password)

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

    def test_admin_cannot_promote_staff_to_registrar_while_one_is_active(self):
        make_registrar()
        staff = make_hod(username="hodtopromote")
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_edit", args=[staff.id]),
            {
                "first_name": staff.first_name,
                "last_name": staff.last_name,
                "email": staff.email,
                "is_active": "on",
                "group": Group.objects.get(name=REGISTRAR_GROUP).id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already an active Registrar")
        staff.refresh_from_db()
        self.assertTrue(staff.groups.filter(name=HOD_GROUP).exists())

    def test_admin_can_promote_staff_to_registrar_after_deactivating_current(self):
        current_registrar = make_registrar()
        staff = make_hod(username="hodtopromote2")
        self.client.login(username="admin", password="pass12345")

        deactivate_response = self.client.post(
            reverse("accounts:staff_edit", args=[current_registrar.id]),
            {
                "first_name": current_registrar.first_name,
                "last_name": current_registrar.last_name,
                "email": current_registrar.email,
                # is_active omitted - unchecked checkbox
                "group": Group.objects.get(name=REGISTRAR_GROUP).id,
            },
        )
        self.assertRedirects(deactivate_response, reverse("accounts:manage_staff"))

        promote_response = self.client.post(
            reverse("accounts:staff_edit", args=[staff.id]),
            {
                "first_name": staff.first_name,
                "last_name": staff.last_name,
                "email": staff.email,
                "is_active": "on",
                "group": Group.objects.get(name=REGISTRAR_GROUP).id,
            },
        )
        self.assertRedirects(promote_response, reverse("accounts:manage_staff"))
        staff.refresh_from_db()
        self.assertTrue(staff.groups.filter(name=REGISTRAR_GROUP).exists())

    def test_over_cap_registrar_account_blocks_unrelated_edits_but_allows_deactivating(self):
        # Simulate a pre-existing violation (e.g. from before this cap existed, or
        # created outside the app) rather than going through the form, since the form
        # itself would now refuse to create it.
        first = make_registrar(username="reg_first")
        second = make_registrar(username="reg_second")
        self.client.login(username="admin", password="pass12345")

        blocked_response = self.client.post(
            reverse("accounts:staff_edit", args=[second.id]),
            {
                "first_name": "Renamed",
                "last_name": second.last_name,
                "email": second.email,
                "is_active": "on",
                "group": Group.objects.get(name=REGISTRAR_GROUP).id,
            },
        )
        self.assertEqual(blocked_response.status_code, 200)
        self.assertContains(blocked_response, "multiple active Registrar accounts")
        second.refresh_from_db()
        self.assertEqual(second.first_name, "")

        resolve_response = self.client.post(
            reverse("accounts:staff_edit", args=[second.id]),
            {
                "first_name": second.first_name,
                "last_name": second.last_name,
                "email": second.email,
                # is_active omitted - unchecked checkbox, resolves the violation
                "group": Group.objects.get(name=REGISTRAR_GROUP).id,
            },
        )
        self.assertRedirects(resolve_response, reverse("accounts:manage_staff"))
        second.refresh_from_db()
        self.assertFalse(second.is_active)
        first.refresh_from_db()
        self.assertTrue(first.is_active)

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


class ProfilePageTests(TestCase):
    def test_staff_can_view_own_profile(self):
        hod = make_hod(username="hodprofile")
        self.client.login(username="hodprofile", password="pass12345")
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, hod.email)

    def test_hod_profile_shows_headed_department(self):
        hod = make_hod(username="hodwithdept")
        Department.objects.create(name="Physics", hod=hod)
        self.client.login(username="hodwithdept", password="pass12345")
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "Physics")

    def test_lecturer_profile_has_no_department_row(self):
        make_lecturer(username="lectprofile")
        self.client.login(username="lectprofile", password="pass12345")
        response = self.client.get(reverse("accounts:profile"))
        self.assertNotContains(response, "Department")

    def test_student_redirected_to_own_profile_page(self):
        department = Department.objects.create(name="Chemistry")
        profile = create_student_account(
            matric_number="2023/CSC/060",
            first_name="Sara",
            last_name="Lee",
            email="saralee@example.com",
            department=department,
            entry_level=100,
        )
        profile.user.must_change_password = False
        profile.user.save(update_fields=["must_change_password"])
        self.client.login(username=profile.user.username, password=settings.DEFAULT_PASSWORD)
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, reverse("students:my_profile"))


class DashboardRoutingTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.student_profile = create_student_account(
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
        self.profile = create_student_account(
            matric_number="2023/CSC/060",
            first_name="Ngozi",
            last_name="Eze",
            email="ngozi@example.com",
            department=self.department,
            entry_level=200,
        )
        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)

    def _send_code(self):
        response = self.client.post(reverse("accounts:send_pin_code"))
        match = re.search(r"PIN: (\d{6})", mail.outbox[-1].body)
        return response, match.group(1)

    def _verify(self, pin):
        return self.client.post(reverse("accounts:verify_pin"), {"pin": pin})

    def _change_password(self):
        return self.client.post(
            reverse("accounts:change_password"),
            {"new_password1": "N3wPassw0rd!", "new_password2": "N3wPassw0rd!"},
        )

    def test_send_code_emails_a_pin(self):
        self._send_code()
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.pin_hash)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("PIN", mail.outbox[0].subject)

    def test_verifying_without_sending_code_shows_clear_error(self):
        response = self._verify("123456")
        self.assertContains(response, "No code has been sent yet")

    def test_correct_pin_allows_password_change(self):
        _, pin = self._send_code()
        self._verify(pin)
        self._change_password()
        self.profile.user.refresh_from_db()
        self.assertFalse(self.profile.user.must_change_password)
        self.assertTrue(self.profile.user.check_password("N3wPassw0rd!"))

    def test_wrong_pin_rejected(self):
        self._send_code()
        response = self._verify("000000")
        self.assertContains(response, "Incorrect code")
        self.profile.user.refresh_from_db()
        self.assertTrue(self.profile.user.must_change_password)

    def test_lockout_after_max_attempts(self):
        _, pin = self._send_code()
        for _ in range(settings.PIN_MAX_ATTEMPTS):
            self._verify("000000")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_pin_locked)

        # Even the correct PIN is rejected once locked.
        response = self._verify(pin)
        self.assertContains(response, "Too many wrong attempts")
        self.profile.user.refresh_from_db()
        self.assertTrue(self.profile.user.must_change_password)

    def test_staff_skips_verify_pin_entirely(self):
        staff = make_admin()
        staff.must_change_password = True
        staff.save(update_fields=["must_change_password"])
        self.client.login(username="admin", password="pass12345")

        # Staff have no student_profile, so the middleware sends them straight to
        # change_password - hitting verify_pin directly should bounce them past it.
        response = self.client.get(reverse("accounts:verify_pin"))
        self.assertRedirects(response, reverse("accounts:change_password"))

        response = self.client.get(reverse("accounts:change_password"))
        self.assertNotContains(response, 'name="pin"')

        response = self.client.post(
            reverse("accounts:change_password"),
            {"new_password1": "N3wPassw0rd!", "new_password2": "N3wPassw0rd!"},
        )
        staff.refresh_from_db()
        self.assertFalse(staff.must_change_password)
