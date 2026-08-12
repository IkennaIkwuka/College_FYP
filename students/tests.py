from accounts.models import ADMIN_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AdmissionRecord, Department, StudentProfile
from .services import create_student_account, seed_admission_record


def make_admin():
    admin = User.objects.create_user(username="admin", email="admin@example.com", password="pass12345")
    admin.groups.add(Group.objects.get(name=ADMIN_GROUP))
    return admin


class BulkImportTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.admin = make_admin()
        self.client.login(username="admin", password="pass12345")

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
    def test_current_level_caps_at_500(self):
        self.assertEqual(self.profile.current_level, 500)


class CreateStudentAccountPasswordTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")

    def test_explicit_password_used_instead_of_default(self):
        profile = create_student_account(
            matric_number="2024/CSC/020",
            first_name="Uche",
            last_name="Nnamdi",
            email="uche@example.com",
            department=self.department,
            entry_level=100,
            password="Ch0senByStudent!",
            must_change_password=False,
        )
        self.assertTrue(profile.user.check_password("Ch0senByStudent!"))
        self.assertFalse(profile.user.check_password(settings.DEFAULT_PASSWORD))
        self.assertFalse(profile.user.must_change_password)

    def test_default_behaviour_unchanged_when_password_omitted(self):
        profile = create_student_account(
            matric_number="2024/CSC/021",
            first_name="Ifeoma",
            last_name="Chukwu",
            email="ifeoma@example.com",
            department=self.department,
            entry_level=100,
        )
        self.assertTrue(profile.user.check_password(settings.DEFAULT_PASSWORD))
        self.assertTrue(profile.user.must_change_password)


class AdmissionRecordPinTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")

    def test_set_and_check_pin_round_trip(self):
        record, raw_pin = seed_admission_record(
            matric_number="2024/CSC/022",
            first_name="Femi",
            last_name="Bello",
            email="femi@example.com",
            department=self.department,
            entry_level=100,
        )
        self.assertTrue(record.check_pin(raw_pin))
        self.assertFalse(record.check_pin("000000"))
        # The raw PIN is never persisted anywhere - only its hash.
        self.assertNotEqual(record.pin_hash, raw_pin)


class SeedAdmissionsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.admin = make_admin()
        self.client.login(username="admin", password="pass12345")

    def _upload(self, content):
        csv_file = SimpleUploadedFile("admissions.csv", content.encode("utf-8"), content_type="text/csv")
        return self.client.post(reverse("students:seed_admissions"), {"csv_file": csv_file})

    def test_valid_csv_creates_records_and_sends_emails(self):
        content = (
            "matric_number,first_name,last_name,email,department,level\n"
            "2024/CSC/030,Bola,Ige,bola@example.com,Computer Science,100\n"
            "2024/CSC/031,Tayo,Ola,tayo@example.com,Computer Science,100\n"
        )
        response = self._upload(content)
        self.assertRedirects(response, reverse("students:seed_admissions"))
        self.assertEqual(AdmissionRecord.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("2024/CSC/030", mail.outbox[0].body + mail.outbox[1].body)

    def test_duplicate_matric_creates_nothing(self):
        AdmissionRecord.objects.create(
            matric_number="2024/CSC/032",
            first_name="X",
            last_name="Y",
            email="existing@example.com",
            department=self.department,
            entry_level=100,
            pin_hash="unused",
        )
        content = (
            "matric_number,first_name,last_name,email,department,level\n"
            "2024/CSC/032,Bola,Ige,bola2@example.com,Computer Science,100\n"
        )
        self._upload(content)
        self.assertEqual(AdmissionRecord.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_already_a_student_creates_nothing(self):
        create_student_account(
            matric_number="2024/CSC/033",
            first_name="Existing",
            last_name="Student",
            email="already@example.com",
            department=self.department,
            entry_level=100,
        )
        content = (
            "matric_number,first_name,last_name,email,department,level\n"
            "2024/CSC/033,Bola,Ige,bola3@example.com,Computer Science,100\n"
        )
        self._upload(content)
        self.assertEqual(AdmissionRecord.objects.count(), 0)
