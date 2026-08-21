from accounts.models import ADMIN_GROUP, HOD_GROUP, REGISTRAR_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Department, StudentProfile
from .services import create_student_account


def make_admin():
    admin = User.objects.create_user(username="admin", email="admin@example.com", password="pass12345")
    admin.groups.add(Group.objects.get(name=ADMIN_GROUP))
    return admin


def make_hod(username="hod1"):
    hod = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    hod.groups.add(Group.objects.get(name=HOD_GROUP))
    return hod


def make_registrar(username="reg1"):
    registrar = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    registrar.groups.add(Group.objects.get(name=REGISTRAR_GROUP))
    return registrar


class RegisterViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")

    def test_admin_forbidden_from_add_student(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("students:register"),
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
            reverse("students:register"),
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
        self.assertRedirects(response, reverse("students:register"))
        self.assertTrue(StudentProfile.objects.filter(matric_number="2023/CSC/099").exists())
        # No PIN is issued at creation anymore - the student requests one themselves
        # at first login (accounts:send_pin_code).
        self.assertEqual(len(mail.outbox), 0)


class BulkImportTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.registrar = make_registrar()
        self.client.login(username="reg1", password="pass12345")

    def _upload(self, content):
        csv_file = SimpleUploadedFile("students.csv", content.encode("utf-8"), content_type="text/csv")
        return self.client.post(reverse("students:bulk_import"), {"csv_file": csv_file})

    def test_valid_csv_creates_students(self):
        content = (
            "matric_number,first_name,last_name,email,department,level\n"
            "2023/CSC/001,Amaka,Obi,amaka@example.com,Computer Science,200\n"
            "2023/CSC/002,Chidi,Eze,chidi@example.com,Computer Science,200\n"
        )
        response = self._upload(content)
        self.assertRedirects(response, reverse("students:bulk_import"))
        self.assertEqual(StudentProfile.objects.count(), 2)

        student = StudentProfile.objects.get(matric_number="2023/CSC/001")
        self.assertTrue(student.user.check_password(settings.DEFAULT_PASSWORD))
        self.assertTrue(student.user.must_change_password)
        self.assertTrue(student.user.groups.filter(name="Student").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_bad_department_creates_nothing(self):
        content = (
            "matric_number,first_name,last_name,email,department,level\n"
            "2023/CSC/003,Amaka,Obi,amaka2@example.com,Physics,200\n"
        )
        self._upload(content)
        self.assertEqual(StudentProfile.objects.count(), 0)

    def test_duplicate_matric_in_file_creates_nothing(self):
        content = (
            "matric_number,first_name,last_name,email,department,level\n"
            "2023/CSC/004,A,B,a@example.com,Computer Science,200\n"
            "2023/CSC/004,C,D,c@example.com,Computer Science,200\n"
        )
        self._upload(content)
        self.assertEqual(StudentProfile.objects.count(), 0)


class LookupTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.admin = make_admin()
        self.client.login(username="admin", password="pass12345")
        self.profile = create_student_account(
            matric_number="2023/CSC/005",
            first_name="Tolu",
            last_name="Ade",
            email="tolu@example.com",
            department=self.department,
            entry_level=300,
        )

    def test_lookup_found(self):
        response = self.client.get(reverse("students:lookup"), {"matric_number": "2023/CSC/005"})
        self.assertContains(response, "Tolu")

    def test_lookup_not_found(self):
        response = self.client.get(reverse("students:lookup"), {"matric_number": "9999/XX/999"})
        self.assertContains(response, "No student found")

    def test_admin_can_force_student_password_reset(self):
        self.profile.user.set_password("someoldpassword")
        self.profile.user.must_change_password = False
        self.profile.user.save()
        response = self.client.post(
            reverse("students:student_force_password_reset", args=[self.profile.id])
        )
        self.assertRedirects(
            response, f"{reverse('students:lookup')}?matric_number={self.profile.matric_number}"
        )
        self.profile.user.refresh_from_db()
        self.assertTrue(self.profile.user.check_password(settings.DEFAULT_PASSWORD))
        self.assertTrue(self.profile.user.must_change_password)

    def test_admin_can_reset_student_pin(self):
        old_hash = self.profile.pin_hash
        self.profile.failed_pin_attempts = 5
        self.profile.save(update_fields=["failed_pin_attempts"])
        response = self.client.post(reverse("students:student_reset_pin", args=[self.profile.id]))
        self.assertRedirects(
            response, f"{reverse('students:lookup')}?matric_number={self.profile.matric_number}"
        )
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.pin_hash, old_hash)
        self.assertEqual(self.profile.failed_pin_attempts, 0)
        self.assertIsNone(self.profile.pin_locked_until)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("PIN", mail.outbox[0].subject)

    def test_registrar_forbidden_from_student_resets(self):
        make_registrar()
        self.client.logout()
        self.client.login(username="reg1", password="pass12345")
        response = self.client.post(
            reverse("students:student_force_password_reset", args=[self.profile.id])
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse("students:student_reset_pin", args=[self.profile.id]))
        self.assertEqual(response.status_code, 403)


class CurrentLevelTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = create_student_account(
            matric_number="2023/CSC/006",
            first_name="Ada",
            last_name="Obi",
            email="ada@example.com",
            department=self.department,
            entry_level=100,
        )

    def test_current_level_matches_entry_level_in_same_session(self):
        self.assertEqual(self.profile.entry_session, settings.CURRENT_SESSION)
        self.assertEqual(self.profile.current_level, 100)

    @override_settings(CURRENT_SESSION="2027/2028")
    def test_current_level_advances_with_session(self):
        self.assertEqual(self.profile.current_level, 300)

    @override_settings(CURRENT_SESSION="2035/2036")
    def test_current_level_caps_at_default_duration(self):
        # self.department has no explicit duration_years - defaults to 4, so the
        # cap is 400, not a fixed 500.
        self.assertEqual(self.profile.current_level, 400)

    def test_current_level_caps_at_departments_own_duration(self):
        law_department = Department.objects.create(name="Law", duration_years=5)
        law_student = create_student_account(
            matric_number="2023/LAW/001", first_name="Chika", last_name="Eze",
            email="chika@example.com", department=law_department, entry_level=100,
        )
        with override_settings(CURRENT_SESSION="2035/2036"):
            self.assertEqual(law_student.current_level, 500)


class DepartmentManagementTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.admin = make_admin()
        self.client.login(username="admin", password="pass12345")

    def test_manage_departments_lists_departments(self):
        response = self.client.get(reverse("students:manage_departments"))
        self.assertContains(response, "Computer Science")

    def test_admin_can_add_department(self):
        response = self.client.post(
            reverse("students:department_add"), {"name": "Physics", "hod": "", "duration_years": 4}
        )
        self.assertRedirects(response, reverse("students:manage_departments"))
        self.assertTrue(Department.objects.filter(name="Physics").exists())

    def test_admin_can_edit_department_and_assign_hod(self):
        hod = make_hod()
        response = self.client.post(
            reverse("students:department_edit", args=[self.department.id]),
            {"name": "Computer Science", "hod": hod.id, "duration_years": 4},
        )
        self.assertRedirects(response, reverse("students:manage_departments"))
        self.department.refresh_from_db()
        self.assertEqual(self.department.hod, hod)

    def test_hod_field_only_offers_hod_group_users(self):
        make_hod()
        non_hod = User.objects.create_user(username="lect1", email="lect1@example.com", password="pass12345")
        response = self.client.get(reverse("students:department_add"))
        hod_queryset = response.context["form"].fields["hod"].queryset
        self.assertIn("hod1", hod_queryset.values_list("username", flat=True))
        self.assertNotIn("lect1", hod_queryset.values_list("username", flat=True))

    def test_non_admin_forbidden(self):
        student = create_student_account(
            matric_number="2023/CSC/090", first_name="A", last_name="B",
            email="ab@example.com", department=self.department, entry_level=100,
        )
        student.user.must_change_password = False
        student.user.save(update_fields=["must_change_password"])
        self.client.login(username=student.user.username, password=settings.DEFAULT_PASSWORD)
        for name in ["students:manage_departments", "students:department_add"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.assertEqual(
            self.client.get(reverse("students:department_edit", args=[self.department.id])).status_code, 403
        )


class MyProfileTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = create_student_account(
            matric_number="2023/CSC/091", first_name="Chidi", last_name="Nwosu",
            email="chidi91@example.com", department=self.department, entry_level=200,
        )
        self.profile.user.must_change_password = False
        self.profile.user.save(update_fields=["must_change_password"])
        self.client.login(username=self.profile.user.username, password=settings.DEFAULT_PASSWORD)

    def test_shows_own_academic_details(self):
        response = self.client.get(reverse("students:my_profile"))
        self.assertContains(response, "2023/CSC/091")
        self.assertContains(response, "Computer Science")

    def test_profile_page_is_view_only(self):
        response = self.client.get(reverse("students:my_profile"))
        self.assertNotContains(response, 'name="save_username"')
        self.assertContains(response, reverse("students:my_profile_edit"))

    def test_edit_page_has_the_editable_forms(self):
        response = self.client.get(reverse("students:my_profile_edit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="save_username"')

    def test_can_update_personal_details(self):
        response = self.client.post(
            reverse("students:my_profile_edit"),
            {"date_of_birth": "2000-01-01", "gender": "M", "phone_number": "08012345678", "address": "Okija"},
        )
        self.assertRedirects(response, reverse("students:my_profile"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone_number, "08012345678")
        self.assertEqual(self.profile.address, "Okija")

    def test_non_student_forbidden(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        self.assertEqual(self.client.get(reverse("students:my_profile")).status_code, 403)

    def test_can_set_preferred_username_without_touching_personal_details(self):
        response = self.client.post(
            reverse("students:my_profile_edit"),
            {"preferred_username": "chidi_n", "save_username": "1"},
        )
        self.assertRedirects(response, reverse("students:my_profile"))
        self.profile.user.refresh_from_db()
        self.assertEqual(self.profile.user.preferred_username, "chidi_n")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone_number, "")

    def test_updating_personal_details_does_not_touch_preferred_username(self):
        self.profile.user.preferred_username = "chidi_n"
        self.profile.user.preferred_username_changed_at = timezone.now()
        self.profile.user.save(update_fields=["preferred_username", "preferred_username_changed_at"])

        response = self.client.post(
            reverse("students:my_profile_edit"),
            {"date_of_birth": "2000-01-01", "gender": "M", "phone_number": "08012345678", "address": "Okija"},
        )
        self.assertRedirects(response, reverse("students:my_profile"))
        self.profile.user.refresh_from_db()
        self.assertEqual(self.profile.user.preferred_username, "chidi_n")


class ManageStudentsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.other_department = Department.objects.create(name="Physics")
        self.profile = create_student_account(
            matric_number="2023/CSC/095", first_name="Ifeoma", last_name="Obiora",
            email="ifeoma95@example.com", department=self.department, entry_level=200,
        )
        self.other_profile = create_student_account(
            matric_number="2023/PHY/010", first_name="Bassey", last_name="Udoh",
            email="bassey10@example.com", department=self.other_department, entry_level=100,
        )
        make_registrar()
        self.client.login(username="reg1", password="pass12345")

    def test_search_by_matric_number(self):
        response = self.client.get(reverse("students:manage_students"), {"q": "2023/CSC/095"})
        self.assertContains(response, "Ifeoma")
        self.assertNotContains(response, "Bassey")

    def test_search_by_name(self):
        response = self.client.get(reverse("students:manage_students"), {"q": "Udoh"})
        self.assertContains(response, "Bassey")
        self.assertNotContains(response, "Ifeoma")

    def test_no_query_shows_all_students(self):
        response = self.client.get(reverse("students:manage_students"))
        self.assertContains(response, "Ifeoma")
        self.assertContains(response, "Bassey")

    def test_filter_by_department(self):
        response = self.client.get(reverse("students:manage_students"), {"department": self.department.id})
        self.assertContains(response, "Ifeoma")
        self.assertNotContains(response, "Bassey")

    def test_filter_by_entry_level(self):
        response = self.client.get(reverse("students:manage_students"), {"entry_level": 100})
        self.assertContains(response, "Bassey")
        self.assertNotContains(response, "Ifeoma")

    def test_search_and_filter_combine(self):
        response = self.client.get(
            reverse("students:manage_students"), {"q": "Obiora", "department": self.department.id}
        )
        self.assertContains(response, "Ifeoma")
        self.assertNotContains(response, "Bassey")

    def test_pagination_limits_to_ten_per_page(self):
        for i in range(20):
            create_student_account(
                matric_number=f"2024/PAG/{i:03d}", first_name=f"Pag{i}", last_name="Tester",
                email=f"pagtest{i}@example.com", department=self.department, entry_level=100,
            )
        response = self.client.get(reverse("students:manage_students"))
        self.assertEqual(len(response.context["profiles"]), 10)

        response_page2 = self.client.get(reverse("students:manage_students"), {"page": 2})
        self.assertEqual(response_page2.context["profiles"].number, 2)

    def test_registrar_can_edit_student(self):
        response = self.client.post(
            reverse("students:student_edit", args=[self.profile.id]),
            {
                "first_name": self.profile.user.first_name,
                "last_name": self.profile.user.last_name,
                "email": self.profile.user.email,
                "matric_number": "2023/CSC/095",
                "department": self.department.id,
                "entry_level": 200,
                "admission_type": "UTME",
                "date_of_birth": "",
                "gender": "",
                "phone_number": "08011112222",
                "address": "Awka",
            },
        )
        self.assertRedirects(response, reverse("students:manage_students"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.phone_number, "08011112222")

    def test_registrar_can_edit_student_name_and_email(self):
        response = self.client.post(
            reverse("students:student_edit", args=[self.profile.id]),
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated.name@example.com",
                "matric_number": self.profile.matric_number,
                "department": self.department.id,
                "entry_level": 200,
                "admission_type": "UTME",
                "date_of_birth": "",
                "gender": "",
                "phone_number": "",
                "address": "",
            },
        )
        self.assertRedirects(response, reverse("students:manage_students"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user.first_name, "Updated")
        self.assertEqual(self.profile.user.last_name, "Name")
        self.assertEqual(self.profile.user.email, "updated.name@example.com")

    def test_editing_matric_number_updates_username(self):
        old_username = self.profile.user.username
        response = self.client.post(
            reverse("students:student_edit", args=[self.profile.id]),
            {
                "first_name": self.profile.user.first_name,
                "last_name": self.profile.user.last_name,
                "email": self.profile.user.email,
                "matric_number": "2023/CSC/199",
                "department": self.department.id,
                "entry_level": 200,
                "admission_type": "UTME",
                "date_of_birth": "",
                "gender": "",
                "phone_number": "",
                "address": "",
            },
        )
        self.assertRedirects(response, reverse("students:manage_students"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.matric_number, "2023/CSC/199")
        self.assertEqual(self.profile.user.username, "2023csc199")
        self.assertNotEqual(self.profile.user.username, old_username)

    def test_editing_without_changing_matric_number_leaves_username_alone(self):
        old_username = self.profile.user.username
        response = self.client.post(
            reverse("students:student_edit", args=[self.profile.id]),
            {
                "first_name": self.profile.user.first_name,
                "last_name": self.profile.user.last_name,
                "email": self.profile.user.email,
                "matric_number": self.profile.matric_number,
                "department": self.department.id,
                "entry_level": 200,
                "admission_type": "UTME",
                "date_of_birth": "",
                "gender": "",
                "phone_number": "08011112222",
                "address": "Awka",
            },
        )
        self.assertRedirects(response, reverse("students:manage_students"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.user.username, old_username)

    def test_non_registrar_forbidden(self):
        make_admin()
        self.client.login(username="admin", password="pass12345")
        self.assertEqual(self.client.get(reverse("students:manage_students")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("students:student_edit", args=[self.profile.id])).status_code, 403
        )
        self.assertEqual(self.client.get(reverse("students:bulk_import")).status_code, 403)
