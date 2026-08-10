from accounts.models import ADMIN_GROUP, User
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Department, StudentProfile
from .services import create_student_account


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
        self.assertTrue(student.user.check_password(settings.DEFAULT_STUDENT_PASSWORD))
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
            level=300,
        )

    def test_lookup_found(self):
        response = self.client.get(reverse("students:lookup"), {"matric_number": "2023/CSC/005"})
        self.assertContains(response, "Tolu")

    def test_lookup_not_found(self):
        response = self.client.get(reverse("students:lookup"), {"matric_number": "9999/XX/999"})
        self.assertContains(response, "No student found")
