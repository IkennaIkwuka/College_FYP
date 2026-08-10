from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from students.models import Department, StudentProfile
from students.services import create_student_account

from .models import ADMIN_GROUP, User


class MatricNumberLoginTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.profile = create_student_account(
            matric_number="2023/CSC/030",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            department=self.department,
            level=300,
        )

    def test_login_with_matric_number(self):
        self.assertTrue(
            self.client.login(username="2023/CSC/030", password=settings.DEFAULT_STUDENT_PASSWORD)
        )

    def test_login_with_username_still_works(self):
        self.assertTrue(
            self.client.login(
                username=self.profile.user.username, password=settings.DEFAULT_STUDENT_PASSWORD
            )
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
            level=300,
        )
        self.client.login(username="2023/CSC/031", password=settings.DEFAULT_STUDENT_PASSWORD)

    def test_redirected_to_change_password(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(response, reverse("accounts:change_password"))

    def test_flag_clears_after_change(self):
        self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": settings.DEFAULT_STUDENT_PASSWORD,
                "new_password1": "N3wPassw0rd!",
                "new_password2": "N3wPassw0rd!",
            },
        )
        self.profile.user.refresh_from_db()
        self.assertFalse(self.profile.user.must_change_password)
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 200)


class AdminOnlyViewsTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")
        self.admin_user = User.objects.create_user(
            username="admin1", email="admin1@example.com", password="pass12345"
        )
        self.admin_user.groups.add(Group.objects.get(name=ADMIN_GROUP))

        self.student_profile = create_student_account(
            matric_number="2023/CSC/032",
            first_name="Ann",
            last_name="Lee",
            email="ann@example.com",
            department=self.department,
            level=200,
        )
        # Skip the forced-password-change redirect for these permission checks -
        # that flow is covered separately in ForcedPasswordChangeTests.
        self.student_profile.user.must_change_password = False
        self.student_profile.user.save(update_fields=["must_change_password"])

    def test_non_admin_forbidden(self):
        self.client.login(username="2023/CSC/032", password=settings.DEFAULT_STUDENT_PASSWORD)
        for name in ["accounts:register", "students:bulk_import", "students:lookup"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_admin_can_add_student(self):
        self.client.login(username="admin1", password="pass12345")
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
