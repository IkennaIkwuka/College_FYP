import re
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from students.models import Department
from students.services import create_student_account

from .forms import PreferredUsernameForm
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

    def test_login_with_punctuation_in_stored_username_still_works(self):
        # A manually-created staff account (typed straight into /admin/) can have
        # a username containing punctuation Django's validator allows (@/./+/-/_)
        # rather than one derived from a slash-stripped matric/staff ID. The
        # lenient-matching regex must not strip that punctuation away and miss it.
        User.objects.create_user(username="j.smith_1", email="jsmith@example.com", password="pass12345")
        self.assertTrue(self.client.login(username="j.smith_1", password="pass12345"))


class SessionExpiryTests(TestCase):
    """FR-AUTH-06: a session idle for 15 minutes stops being valid - same
    settings.LOGIN_LOCKOUT_MINUTES-style value as the other lockouts, applied to
    Django's own session-expiry mechanism rather than a custom field."""

    def setUp(self):
        # make_lecturer, not a freshly created student - a new student account
        # has must_change_password=True and would get redirected into the forced
        # password-change flow, which is unrelated to what's being tested here.
        self.user = make_lecturer(username="sessionexp1")
        self.client.login(username="sessionexp1", password="pass12345")

    def test_still_logged_in_within_window(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_session_expires_after_idle_period(self):
        session = Session.objects.get(session_key=self.client.session.session_key)
        session.expire_date = timezone.now() - timedelta(minutes=1)
        session.save(update_fields=["expire_date"])

        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_activity_extends_the_window(self):
        self.client.get(reverse("dashboard"))
        session = Session.objects.get(session_key=self.client.session.session_key)
        self.assertGreater(session.expire_date, timezone.now() + timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES - 1))


class LoginLockoutTests(TestCase):
    """FR-AUTH-05: lock an account out after settings.LOGIN_MAX_ATTEMPTS consecutive
    wrong-password attempts, same shape as the existing PIN/email-change lockouts."""

    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = create_student_account(
            matric_number="2023/CSC/032",
            first_name="Amaka",
            last_name="Obi",
            email="amaka@example.com",
            department=self.department,
            entry_level=300,
        )
        self.username = self.profile.user.username

    def test_lockout_after_max_failed_attempts(self):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            self.assertFalse(self.client.login(username=self.username, password="wrong-password"))
        # Even the correct password is rejected once locked.
        self.assertFalse(self.client.login(username=self.username, password=settings.DEFAULT_PASSWORD))
        self.profile.user.refresh_from_db()
        self.assertTrue(self.profile.user.is_login_locked)

    def test_fewer_than_max_attempts_does_not_lock(self):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
            self.client.login(username=self.username, password="wrong-password")
        self.assertTrue(self.client.login(username=self.username, password=settings.DEFAULT_PASSWORD))

    def test_successful_login_resets_attempt_counter(self):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS - 1):
            self.client.login(username=self.username, password="wrong-password")
        self.assertTrue(self.client.login(username=self.username, password=settings.DEFAULT_PASSWORD))
        self.profile.user.refresh_from_db()
        self.assertEqual(self.profile.user.failed_login_attempts, 0)

    def test_lockout_clears_after_cooldown(self):
        user = self.profile.user
        user.failed_login_attempts = settings.LOGIN_MAX_ATTEMPTS
        user.login_locked_until = timezone.now() - timedelta(minutes=1)
        user.save(update_fields=["failed_login_attempts", "login_locked_until"])
        self.assertTrue(self.client.login(username=self.username, password=settings.DEFAULT_PASSWORD))

    def test_inactive_account_correct_password_not_counted_as_failed_attempt(self):
        user = self.profile.user
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.client.login(username=self.username, password=settings.DEFAULT_PASSWORD)
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 0)


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
        response = self.client.get(reverse("dashboard"), follow=True)
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
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student dashboard.")

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
            self.client.get(reverse("accounts:staff_detail", args=[staff.id])).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("accounts:staff_force_password_reset", args=[staff.id])
            ).status_code,
            403,
        )

    def test_admin_can_add_staff(self):
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_add"),
            {
                "first_name": "New",
                "last_name": "Lecturer",
                "email": "newlect@example.com",
                "group": Group.objects.get(name=LECTURER_GROUP).id,
            },
        )
        self.assertRedirects(response, reverse("accounts:manage_staff"))
        new_staff = User.objects.get(email="newlect@example.com")
        self.assertRegex(new_staff.staff_id, r"^LU-LC-\d{2}-\d{4}$")
        self.assertEqual(new_staff.username, re.sub(r"[^a-z0-9]", "", new_staff.staff_id.lower()))
        self.assertTrue(new_staff.groups.filter(name=LECTURER_GROUP).exists())

    def test_staff_ids_are_sequential_within_role_and_year(self):
        self.client.login(username="admin", password="pass12345")
        for i in range(2):
            self.client.post(
                reverse("accounts:staff_add"),
                {
                    "first_name": "Lect",
                    "last_name": str(i),
                    "email": f"lect{i}@example.com",
                    "group": Group.objects.get(name=LECTURER_GROUP).id,
                },
            )
        first = User.objects.get(email="lect0@example.com")
        second = User.objects.get(email="lect1@example.com")
        self.assertTrue(first.staff_id.endswith("-0001"))
        self.assertTrue(second.staff_id.endswith("-0002"))

    def test_admin_can_add_registrar_when_none_active(self):
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("accounts:staff_add"),
            {
                "first_name": "First",
                "last_name": "Registrar",
                "email": "firstreg@example.com",
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
        self.assertRedirects(response, reverse("accounts:staff_detail", args=[staff.id]))
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
        self.assertRedirects(response, reverse("accounts:staff_detail", args=[staff.id]))

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
        self.assertRedirects(deactivate_response, reverse("accounts:staff_detail", args=[current_registrar.id]))

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
        self.assertRedirects(promote_response, reverse("accounts:staff_detail", args=[staff.id]))
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
        self.assertRedirects(resolve_response, reverse("accounts:staff_detail", args=[second.id]))
        second.refresh_from_db()
        self.assertFalse(second.is_active)
        first.refresh_from_db()
        self.assertTrue(first.is_active)

    def test_staff_detail_shows_read_only_record(self):
        staff = make_hod(username="hodtoview")
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("accounts:staff_detail", args=[staff.id]))
        self.assertContains(response, "hodtoview")
        self.assertContains(response, staff.email)
        self.assertContains(response, "Edit")

    def test_staff_detail_shows_preferred_username_column(self):
        staff = make_hod(username="hodwithpreferred")
        staff.preferred_username = "hod_pref"
        staff.save(update_fields=["preferred_username"])
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("accounts:staff_detail", args=[staff.id]))
        self.assertContains(response, "Preferred Username")
        self.assertContains(response, "hod_pref")

    def test_manage_staff_list_links_to_detail_not_edit(self):
        staff = make_hod(username="hodinlist")
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("accounts:manage_staff"))
        self.assertContains(response, reverse("accounts:staff_detail", args=[staff.id]))

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
            User(email="a@example.com", first_name="A", last_name="One", staff_id="LU-LC-26-0003")
        )
        user.save()

        self.assertEqual(user.staff_id, "LU-LC-26-0003")
        self.assertEqual(user.username, "lulc260003")

    def test_default_password_and_forced_change(self):
        user = assign_staff_identity(
            User(email="c@example.com", first_name="C", last_name="Three", staff_id="LU-LC-26-0004")
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
                "groups": [Group.objects.get(name=LECTURER_GROUP).id],
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="grace@example.com")
        self.assertRegex(user.staff_id, r"^LU-LC-\d{2}-\d{4}$")
        self.assertEqual(user.username, re.sub(r"[^a-z0-9]", "", user.staff_id.lower()))
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.groups.filter(name=LECTURER_GROUP).exists())

    def test_admin_add_form_rejects_zero_or_multiple_staff_groups(self):
        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace2@example.com",
                "groups": [
                    Group.objects.get(name=LECTURER_GROUP).id,
                    Group.objects.get(name=HOD_GROUP).id,
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="grace2@example.com").exists())
        self.assertContains(response, "Select exactly one staff role.")

        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace3@example.com",
                "groups": [],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="grace3@example.com").exists())
        self.assertContains(response, "Select exactly one staff role.")


class ProfilePageTests(TestCase):
    def test_staff_can_view_own_profile(self):
        hod = make_hod(username="hodprofile")
        self.client.login(username="hodprofile", password="pass12345")
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, hod.email)

    def test_hod_profile_shows_headed_department(self):
        hod = make_hod(username="hodwithdept")
        Department.objects.create(name="Physics", hod=hod)
        self.client.login(username="hodwithdept", password="pass12345")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Physics")

    def test_lecturer_profile_has_no_department_row(self):
        make_lecturer(username="lectprofile")
        self.client.login(username="lectprofile", password="pass12345")
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, "Department")

    def test_neutral_profile_url_serves_student_content_directly(self):
        # The URL itself must stay role-neutral - no redirect to a role-specific
        # path, same reasoning as the earlier /login/ move (ec4631b): the address
        # bar shouldn't reveal what kind of account this is.
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
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2023/CSC/060")
        self.assertContains(response, "Academic Details")

    def test_profile_page_is_view_only(self):
        make_lecturer(username="viewonly1")
        self.client.login(username="viewonly1", password="pass12345")
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, 'name="save_profile"')
        self.assertNotContains(response, 'name="save_username"')
        self.assertContains(response, reverse("profile_edit"))

    def test_edit_page_has_the_editable_forms(self):
        make_lecturer(username="editpage1")
        self.client.login(username="editpage1", password="pass12345")
        response = self.client.get(reverse("profile_edit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="save_profile"')
        self.assertContains(response, 'name="save_username"')

    def test_view_page_has_no_change_email_link(self):
        make_lecturer(username="viewnoemail1")
        self.client.login(username="viewnoemail1", password="pass12345")
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, reverse("accounts:request_email_change"))

    def test_edit_page_has_change_email_link(self):
        make_lecturer(username="editemail1")
        self.client.login(username="editemail1", password="pass12345")
        response = self.client.get(reverse("profile_edit"))
        self.assertContains(response, reverse("accounts:request_email_change"))

    def test_staff_can_update_personal_info(self):
        make_lecturer(username="staffpersonal1")
        self.client.login(username="staffpersonal1", password="pass12345")
        response = self.client.post(
            reverse("profile_edit"),
            {
                "save_profile": "1",
                "phone_number": "08012345678",
                "date_of_birth": "1998-05-14",
                "gender": "M",
            },
        )
        self.assertRedirects(response, reverse("profile"))
        user = User.objects.get(username="staffpersonal1")
        self.assertEqual(user.phone_number, "08012345678")
        self.assertEqual(str(user.date_of_birth), "1998-05-14")
        self.assertEqual(user.gender, "M")


class NavbarSettingsMenuTests(TestCase):
    def test_toggle_has_dropdown_caret(self):
        make_lecturer(username="navcaret1")
        self.client.login(username="navcaret1", password="pass12345")
        response = self.client.get(reverse("dashboard"), follow=True)
        self.assertContains(response, "dropdown-toggle")

    def test_toggle_shows_initials_from_name(self):
        user = User.objects.create_user(
            username="navinit1", email="navinit1@example.com", password="pass12345",
            first_name="Grace", last_name="Okafor",
        )
        user.groups.add(Group.objects.get(name=LECTURER_GROUP))
        self.client.login(username="navinit1", password="pass12345")
        response = self.client.get(reverse("dashboard"), follow=True)
        self.assertContains(response, ">GO<")

    def test_toggle_falls_back_to_username_initial_without_a_name(self):
        make_lecturer(username="navinit2")
        self.client.login(username="navinit2", password="pass12345")
        response = self.client.get(reverse("dashboard"), follow=True)
        self.assertContains(response, ">N<")


class PreferredUsernameLockedUntilTests(TestCase):
    def test_none_when_never_changed(self):
        hod = make_hod(username="pulock1")
        self.assertIsNone(hod.preferred_username_locked_until)

    def test_future_right_after_a_change(self):
        hod = make_hod(username="pulock2")
        hod.preferred_username = "adaeze"
        hod.preferred_username_changed_at = timezone.now()
        hod.save(update_fields=["preferred_username", "preferred_username_changed_at"])
        self.assertIsNotNone(hod.preferred_username_locked_until)
        self.assertGreater(hod.preferred_username_locked_until, timezone.now())

    def test_none_again_once_cooldown_has_passed(self):
        hod = make_hod(username="pulock3")
        hod.preferred_username = "adaeze"
        hod.preferred_username_changed_at = timezone.now() - timedelta(
            days=settings.PREFERRED_USERNAME_COOLDOWN_DAYS + 1
        )
        hod.save(update_fields=["preferred_username", "preferred_username_changed_at"])
        self.assertIsNone(hod.preferred_username_locked_until)


class PreferredUsernameFormTests(TestCase):
    def setUp(self):
        self.hod = make_hod(username="puform1")
        self.other = make_lecturer(username="puform2")

    def test_accepts_a_valid_new_value(self):
        form = PreferredUsernameForm({"preferred_username": "AdaEze"}, user=self.hod)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["preferred_username"], "adaeze")

    def test_rejects_duplicate_against_another_users_username(self):
        form = PreferredUsernameForm({"preferred_username": self.other.username}, user=self.hod)
        self.assertFalse(form.is_valid())
        self.assertIn("already taken", str(form.errors))

    def test_rejects_duplicate_against_another_users_preferred_username(self):
        self.other.preferred_username = "takenname"
        self.other.preferred_username_changed_at = timezone.now()
        self.other.save(update_fields=["preferred_username", "preferred_username_changed_at"])
        form = PreferredUsernameForm({"preferred_username": "TakenName"}, user=self.hod)
        self.assertFalse(form.is_valid())
        self.assertIn("already taken", str(form.errors))

    def test_rejects_while_on_cooldown(self):
        self.hod.preferred_username = "originalname"
        self.hod.preferred_username_changed_at = timezone.now()
        self.hod.save(update_fields=["preferred_username", "preferred_username_changed_at"])
        form = PreferredUsernameForm({"preferred_username": "newname"}, user=self.hod)
        self.assertFalse(form.is_valid())
        self.assertIn("change your preferred username again", str(form.errors))

    def test_resubmitting_same_value_while_on_cooldown_is_allowed(self):
        self.hod.preferred_username = "originalname"
        self.hod.preferred_username_changed_at = timezone.now()
        self.hod.save(update_fields=["preferred_username", "preferred_username_changed_at"])
        form = PreferredUsernameForm({"preferred_username": "originalname"}, user=self.hod)
        self.assertTrue(form.is_valid(), form.errors)

    def test_clearing_to_blank_is_accepted(self):
        form = PreferredUsernameForm({"preferred_username": ""}, user=self.hod)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["preferred_username"])

    def test_field_is_not_readonly_when_no_cooldown(self):
        form = PreferredUsernameForm(user=self.hod)
        self.assertNotIn("readonly", form.fields["preferred_username"].widget.attrs)

    def test_field_is_readonly_during_cooldown(self):
        self.hod.preferred_username = "originalname"
        self.hod.preferred_username_changed_at = timezone.now()
        self.hod.save(update_fields=["preferred_username", "preferred_username_changed_at"])
        form = PreferredUsernameForm(user=self.hod)
        self.assertTrue(form.fields["preferred_username"].widget.attrs.get("readonly"))
        self.assertEqual(form.initial["preferred_username"], "originalname")


class PreferredUsernameViewTests(TestCase):
    def test_staff_can_set_preferred_username(self):
        make_hod(username="puview1")
        self.client.login(username="puview1", password="pass12345")
        response = self.client.post(reverse("profile_edit"), {"preferred_username": "hodada"})
        self.assertRedirects(response, reverse("profile"))
        user = User.objects.get(username="puview1")
        self.assertEqual(user.preferred_username, "hodada")

    def test_second_change_within_cooldown_is_rejected(self):
        make_hod(username="puview2")
        self.client.login(username="puview2", password="pass12345")
        self.client.post(reverse("profile_edit"), {"preferred_username": "firstpick"})
        response = self.client.post(reverse("profile_edit"), {"preferred_username": "secondpick"})
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="puview2")
        self.assertEqual(user.preferred_username, "firstpick")


class LenientUsernameBackendPreferredUsernameTests(TestCase):
    def test_login_via_preferred_username(self):
        hod = make_hod(username="lubpu1")
        hod.preferred_username = "adaeze"
        hod.preferred_username_changed_at = timezone.now()
        hod.save(update_fields=["preferred_username", "preferred_username_changed_at"])
        self.assertTrue(self.client.login(username="AdaEze", password="pass12345"))

    def test_login_via_derived_username_still_works(self):
        make_hod(username="lubpu2")
        self.assertTrue(self.client.login(username="lubpu2", password="pass12345"))


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

    def test_admin_sees_admin_dashboard(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "IT Admin dashboard.")

    def test_hod_sees_hod_dashboard(self):
        make_hod()
        self.client.login(username="hod1", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HOD dashboard.")

    def test_lecturer_sees_lecturer_dashboard(self):
        make_lecturer()
        self.client.login(username="lect1", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lecturer dashboard.")

    def test_student_sees_student_dashboard(self):
        self.client.login(username=self.student_profile.user.username, password=settings.DEFAULT_PASSWORD)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student dashboard.")

    def test_hod_takes_priority_over_lecturer(self):
        # A department head is usually also a Lecturer - HOD should win.
        user = make_hod(username="hodlect")
        user.groups.add(Group.objects.get(name=LECTURER_GROUP))
        self.client.login(username="hodlect", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "HOD dashboard.")

    def test_registrar_sees_registrar_dashboard(self):
        make_registrar()
        self.client.login(username="reg1", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrar dashboard.")

    def test_bursar_sees_bursar_dashboard(self):
        make_bursar()
        self.client.login(username="bursar1", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bursar dashboard.")

    def test_dean_sees_dean_dashboard(self):
        make_dean()
        self.client.login(username="dean1", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dean dashboard.")

    def test_dean_takes_priority_over_hod(self):
        # A Dean is senior academic staff, often also an HOD in a smaller faculty -
        # Dean should win.
        user = make_dean(username="deanhod")
        user.groups.add(Group.objects.get(name=HOD_GROUP))
        self.client.login(username="deanhod", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Dean dashboard.")

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


class ForgotPasswordTests(TestCase):
    def setUp(self):
        self.user = make_lecturer(username="forgotpw1")

    def _request(self, email):
        return self.client.post(reverse("accounts:forgot_password"), {"email": email}, follow=True)

    def test_request_sends_reset_email_to_registered_user(self):
        response = self._request(self.user.email)
        self.assertRedirects(response, reverse("accounts:forgot_password_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_request_with_unregistered_email_gives_same_response_and_sends_nothing(self):
        response = self._request("nobody@example.com")
        self.assertRedirects(response, reverse("accounts:forgot_password_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_link_allows_setting_new_password_and_logs_in(self):
        self._request(self.user.email)
        match = re.search(r"(/accounts/forgot-password/\S+/\S+/)", mail.outbox[0].body)
        reset_url = match.group(1)

        response = self.client.get(reset_url, follow=True)
        set_password_url = response.redirect_chain[-1][0]
        response = self.client.post(
            set_password_url,
            {"new_password1": "N3wPassw0rd!", "new_password2": "N3wPassw0rd!"},
            follow=True,
        )
        self.assertRedirects(response, reverse("accounts:forgot_password_complete"))

        self.client.logout()
        self.assertTrue(self.client.login(username=self.user.username, password="N3wPassw0rd!"))

    def test_reset_clears_must_change_password_flag(self):
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])

        self._request(self.user.email)
        match = re.search(r"(/accounts/forgot-password/\S+/\S+/)", mail.outbox[0].body)
        response = self.client.get(match.group(1), follow=True)
        set_password_url = response.redirect_chain[-1][0]
        self.client.post(
            set_password_url,
            {"new_password1": "N3wPassw0rd!", "new_password2": "N3wPassw0rd!"},
        )

        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)


class SelfChangePasswordTests(TestCase):
    def setUp(self):
        self.user = make_lecturer(username="selfchpw1")
        self.client.login(username="selfchpw1", password="pass12345")

    def _change(self, old_password, new_password="N3wPassw0rd!"):
        return self.client.post(
            reverse("accounts:self_change_password"),
            {"old_password": old_password, "new_password1": new_password, "new_password2": new_password},
        )

    def test_wrong_current_password_rejected(self):
        response = self._change("wrongpassword")
        self.assertContains(response, "old password")
        self.assertTrue(self.client.login(username="selfchpw1", password="pass12345"))

    def test_correct_current_password_changes_password_and_stays_logged_in(self):
        response = self._change("pass12345")
        self.assertRedirects(response, reverse("profile"))
        # update_session_auth_hash means the session survives the password change -
        # a follow-up request should still be authenticated, not bounced to login.
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        self.assertTrue(self.client.login(username="selfchpw1", password="N3wPassw0rd!"))

    def test_forced_change_password_view_has_no_old_password_field(self):
        # Regression check - accounts:change_password (first-login/admin-forced
        # reset, and forgot-password's confirm step) must stay untouched by the
        # self-service form added alongside it.
        response = self.client.get(reverse("accounts:change_password"))
        self.assertNotContains(response, 'name="old_password"')


class EmailChangeTests(TestCase):
    def setUp(self):
        self.user = make_lecturer(username="emailchg1")
        self.client.login(username="emailchg1", password="pass12345")

    def _request_change(self, new_email="new.address@example.com"):
        response = self.client.post(reverse("accounts:request_email_change"), {"new_email": new_email})
        match = re.search(r"Code: (\d{6})", mail.outbox[-1].body)
        return response, match.group(1)

    def _confirm(self, code):
        return self.client.post(reverse("accounts:confirm_email_change"), {"code": code})

    def test_request_change_emails_code_to_new_address_only(self):
        self._request_change("new.address@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.pending_email, "new.address@example.com")
        self.assertNotEqual(self.user.email, "new.address@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new.address@example.com"])

    def test_correct_code_updates_email_and_notifies_old_address(self):
        old_email = self.user.email
        _, code = self._request_change("new.address@example.com")
        response = self._confirm(code)
        self.assertRedirects(response, reverse("profile"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new.address@example.com")
        self.assertEqual(self.user.pending_email, "")
        self.assertIsNotNone(self.user.email_changed_at)

        # Second email is the old-address notice.
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, [old_email])

    def test_wrong_code_rejected(self):
        self._request_change("new.address@example.com")
        response = self._confirm("000000")
        self.assertContains(response, "Incorrect code")
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.email, "new.address@example.com")

    def test_lockout_after_max_attempts(self):
        _, code = self._request_change("new.address@example.com")
        for _ in range(settings.EMAIL_CHANGE_CODE_MAX_ATTEMPTS):
            self._confirm("000000")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_change_locked)

        # Even the correct code is rejected once locked.
        response = self._confirm(code)
        self.assertContains(response, "Too many wrong attempts")
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.email, "new.address@example.com")

    def test_cooldown_blocks_second_change(self):
        _, code = self._request_change("new.address@example.com")
        self._confirm(code)

        response = self.client.post(
            reverse("accounts:request_email_change"), {"new_email": "another@example.com"}
        )
        self.assertContains(response, "change your email again on")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new.address@example.com")

    # Enumeration-oracle fix: an email already belonging to someone else must look
    # identical, from the requester's side, to a genuinely free one - same redirect,
    # same message, no code actually sent, no state that could later confirm.
    def test_taken_email_redirects_same_as_free_email(self):
        other = make_lecturer(username="emailchg_taken")
        response = self.client.post(
            reverse("accounts:request_email_change"), {"new_email": other.email}
        )
        self.assertRedirects(response, reverse("accounts:confirm_email_change"))

    def test_taken_email_shows_same_success_message(self):
        other = make_lecturer(username="emailchg_taken2")
        response = self.client.post(
            reverse("accounts:request_email_change"), {"new_email": other.email}, follow=True
        )
        self.assertContains(response, f"Code sent to {other.email}")

    def test_taken_email_sends_no_code_and_stores_no_hash(self):
        other = make_lecturer(username="emailchg_taken3")
        self.client.post(reverse("accounts:request_email_change"), {"new_email": other.email})
        self.assertEqual(len(mail.outbox), 0)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email_change_code_hash, "")

    def test_taken_email_any_code_rejected_as_incorrect_not_missing(self):
        other = make_lecturer(username="emailchg_taken4")
        self.client.post(reverse("accounts:request_email_change"), {"new_email": other.email})
        response = self._confirm("123456")
        self.assertContains(response, "Incorrect code")
        self.assertNotContains(response, "No code has been sent yet")

    def test_taken_email_never_completes_no_cooldown_starts(self):
        other = make_lecturer(username="emailchg_taken5")
        self.client.post(reverse("accounts:request_email_change"), {"new_email": other.email})
        self._confirm("123456")
        self.user.refresh_from_db()
        self.assertIsNone(self.user.email_changed_at)
        self.assertNotEqual(self.user.email, other.email)

    def test_own_current_email_still_shows_distinct_message(self):
        # Not a leak - this only reveals info about the requester's own account,
        # which they already know, so it's fine to keep this one specific.
        response = self.client.post(
            reverse("accounts:request_email_change"), {"new_email": self.user.email}
        )
        self.assertContains(response, "already your current email")
