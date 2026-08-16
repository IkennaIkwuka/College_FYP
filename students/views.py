import csv
import io

from accounts.decorators import admin_required, registrar_required, student_required
from accounts.services import force_password_reset
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import BulkImportForm, DepartmentForm, FacultyForm, StudentEditForm, StudentProfileForm
from .models import ADMISSION_TYPE_CHOICES, LEVEL_CHOICES, Department, Faculty, StudentProfile
from .services import create_student_account, reset_student_pin

REQUIRED_COLUMNS = {"matric_number", "first_name", "last_name", "email", "department", "level"}
OPTIONAL_COLUMNS = {"date_of_birth", "gender", "phone_number", "address"}
VALID_LEVELS = {str(level) for level, _ in LEVEL_CHOICES}


def _validate_row(row, seen_matrics, seen_emails):
    """Check one CSV row for problems without creating anything yet.

    seen_matrics/seen_emails are shared across every row in the file (passed in
    by the caller), so this also catches two rows in the SAME upload trying to
    use the same matric number or email - not just clashes with existing students.
    """
    errors = []

    matric_number = (row.get("matric_number") or "").strip().upper()
    if not matric_number:
        errors.append("matric_number is required")
    elif matric_number in seen_matrics:
        errors.append(f"duplicate matric_number {matric_number} in file")
    elif StudentProfile.objects.filter(matric_number=matric_number).exists():
        errors.append(f"matric_number {matric_number} already exists")
    else:
        seen_matrics.add(matric_number)

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif email in seen_emails:
        errors.append(f"duplicate email {email} in file")
    elif StudentProfile.objects.filter(user__email__iexact=email).exists():
        errors.append(f"email {email} already exists")
    else:
        seen_emails.add(email)

    if not (row.get("first_name") or "").strip():
        errors.append("first_name is required")
    if not (row.get("last_name") or "").strip():
        errors.append("last_name is required")

    department_name = (row.get("department") or "").strip()
    department = Department.objects.filter(name__iexact=department_name).first()
    if not department:
        errors.append(f"department '{department_name}' does not exist")

    level = (row.get("level") or "").strip()
    if level not in VALID_LEVELS:
        errors.append(f"level '{level}' must be one of {sorted(VALID_LEVELS)}")

    return errors


@admin_required
def bulk_import(request):
    if request.method == "POST":
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            decoded = io.TextIOWrapper(request.FILES["csv_file"].file, encoding="utf-8-sig")
            reader = csv.DictReader(decoded)

            if not REQUIRED_COLUMNS.issubset(set(reader.fieldnames or [])):
                messages.error(
                    request,
                    f"CSV must include columns: {', '.join(sorted(REQUIRED_COLUMNS))}",
                )
            else:
                rows = list(reader)
                errors = []
                seen_matrics = set()
                seen_emails = set()
                # start=2 because row 1 of the file is the header row, so the first
                # data row is what a spreadsheet program would call row 2.
                for i, row in enumerate(rows, start=2):
                    for error in _validate_row(row, seen_matrics, seen_emails):
                        errors.append(f"Row {i}: {error}")

                if errors:
                    # Validate the WHOLE file before creating anything: if even one row
                    # is bad, show every problem at once and create nothing, rather than
                    # partially importing and leaving the admin to guess what succeeded.
                    for error in errors:
                        messages.error(request, error)
                else:
                    # transaction.atomic() makes all these creates succeed or fail together -
                    # if row 50 of 100 somehow raised an unexpected error, rows 1-49 would be
                    # rolled back too instead of leaving a half-imported file.
                    created = []
                    with transaction.atomic():
                        for row in rows:
                            department = Department.objects.get(name__iexact=row["department"].strip())
                            optional_fields = {
                                field: row[field].strip()
                                for field in OPTIONAL_COLUMNS
                                if row.get(field, "").strip()
                            }
                            profile, raw_pin = create_student_account(
                                matric_number=row["matric_number"],
                                first_name=row["first_name"].strip(),
                                last_name=row["last_name"].strip(),
                                email=row["email"].strip(),
                                department=department,
                                entry_level=int(row["level"]),
                                **optional_fields,
                            )
                            created.append((profile, raw_pin))

                    # PIN emails go out AFTER the transaction commits - sending a batch of
                    # emails while holding a write lock open is expensive under SQLite's
                    # single-writer model, and a send_mail failure shouldn't roll back
                    # student accounts that are already correctly persisted.
                    failed_emails = []
                    for profile, raw_pin in created:
                        try:
                            send_mail(
                                subject="Your LU-SIMS PIN",
                                message=(
                                    f"Matric number: {profile.matric_number}\n"
                                    f"PIN: {raw_pin}\n\n"
                                    f'Log in with your username "{profile.user.username}" and the '
                                    f'default password "{settings.DEFAULT_PASSWORD}", then enter this '
                                    "PIN when prompted to set your own password."
                                ),
                                from_email=None,
                                recipient_list=[profile.user.email],
                            )
                        except Exception:
                            failed_emails.append(profile.user.email)

                    messages.success(request, f"Imported {len(rows)} students.")
                    if failed_emails:
                        messages.warning(
                            request,
                            f"Could not send the PIN email to: {', '.join(failed_emails)}. "
                            "Follow up with them manually.",
                        )
                    return redirect("students:bulk_import")
    else:
        form = BulkImportForm()

    return render(
        request,
        "students/bulk_import.html",
        {"form": form, "default_password": settings.DEFAULT_PASSWORD},
    )


@admin_required
def lookup(request):
    matric_number = request.GET.get("matric_number", "").strip().upper()
    profile = None
    registrations = None

    if matric_number:
        profile = StudentProfile.objects.select_related("user", "department").filter(
            matric_number=matric_number
        ).first()
        if profile is None:
            messages.error(request, "No student found with that matric number.")
        else:
            registrations = profile.registrations.select_related("course")

    return render(
        request,
        "students/lookup.html",
        {"matric_number": matric_number, "profile": profile, "registrations": registrations},
    )


def _back_to_lookup(profile):
    return redirect(f"{reverse('students:lookup')}?matric_number={profile.matric_number}")


@admin_required
def student_force_password_reset(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)

    if request.method == "POST":
        force_password_reset(profile.user)
        messages.success(
            request,
            f"Password reset for {profile.matric_number}. They'll need to log in with the "
            f'default password ("{settings.DEFAULT_PASSWORD}") and set a new one.',
        )
    return _back_to_lookup(profile)


@admin_required
def student_reset_pin(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)

    if request.method == "POST":
        raw_pin = reset_student_pin(profile)
        try:
            send_mail(
                subject="Your LU-SIMS PIN",
                message=(
                    f"Matric number: {profile.matric_number}\n"
                    f"PIN: {raw_pin}\n\n"
                    f'Log in with your username "{profile.user.username}" and the '
                    f'default password "{settings.DEFAULT_PASSWORD}", then enter this '
                    "PIN when prompted to set your own password."
                ),
                from_email=None,
                recipient_list=[profile.user.email],
            )
            messages.success(request, f"PIN reset for {profile.matric_number}. New PIN emailed.")
        except Exception:
            messages.warning(
                request,
                f"PIN reset, but the email to {profile.user.email} failed. Follow up manually.",
            )
    return _back_to_lookup(profile)


@admin_required
def manage_faculties(request):
    faculties = Faculty.objects.all()
    return render(request, "students/manage_faculties.html", {"faculties": faculties})


@admin_required
def faculty_add(request):
    if request.method == "POST":
        form = FacultyForm(request.POST)
        if form.is_valid():
            faculty = form.save()
            messages.success(request, f"Added {faculty.name}.")
            return redirect("students:manage_faculties")
    else:
        form = FacultyForm()

    return render(request, "students/faculty_form.html", {"form": form, "title": "Add Faculty"})


@admin_required
def faculty_edit(request, pk):
    faculty = get_object_or_404(Faculty, pk=pk)

    if request.method == "POST":
        form = FacultyForm(request.POST, instance=faculty)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {faculty.name}.")
            return redirect("students:manage_faculties")
    else:
        form = FacultyForm(instance=faculty)

    return render(request, "students/faculty_form.html", {"form": form, "title": f"Edit {faculty.name}"})


@admin_required
def manage_departments(request):
    departments = Department.objects.all()
    return render(request, "students/manage_departments.html", {"departments": departments})


@admin_required
def department_add(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(request, f"Added {department.name}.")
            return redirect("students:manage_departments")
    else:
        form = DepartmentForm()

    return render(request, "students/department_form.html", {"form": form, "title": "Add Department"})


@admin_required
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)

    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {department.name}.")
            return redirect("students:manage_departments")
    else:
        form = DepartmentForm(instance=department)

    return render(
        request, "students/department_form.html", {"form": form, "title": f"Edit {department.name}"}
    )


@registrar_required
def manage_students(request):
    query = request.GET.get("q", "").strip()
    department_id = request.GET.get("department", "").strip()
    entry_level = request.GET.get("entry_level", "").strip()
    admission_type = request.GET.get("admission_type", "").strip()

    profiles = StudentProfile.objects.select_related("user", "department").order_by("matric_number")
    if query:
        profiles = profiles.filter(
            Q(matric_number__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
        )
    if department_id:
        profiles = profiles.filter(department_id=department_id)
    if entry_level:
        profiles = profiles.filter(entry_level=entry_level)
    if admission_type:
        profiles = profiles.filter(admission_type=admission_type)

    paginator = Paginator(profiles, 10)
    profiles = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    return render(
        request,
        "students/manage_students.html",
        {
            "query": query,
            "profiles": profiles,
            "querystring": querystring,
            "departments": Department.objects.all(),
            "levels": LEVEL_CHOICES,
            "admission_types": ADMISSION_TYPE_CHOICES,
            "selected_department": department_id,
            "selected_entry_level": entry_level,
            "selected_admission_type": admission_type,
        },
    )


@registrar_required
def student_edit(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)

    if request.method == "POST":
        form = StudentEditForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {profile.matric_number}.")
            return redirect("students:manage_students")
    else:
        form = StudentEditForm(instance=profile)

    return render(request, "students/student_form.html", {"form": form, "profile": profile})


@student_required
def my_profile(request):
    profile = request.user.student_profile

    if request.method == "POST":
        form = StudentProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("students:my_profile")
    else:
        form = StudentProfileForm(instance=profile)

    return render(request, "students/my_profile.html", {"form": form, "profile": profile})
