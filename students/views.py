import csv
import io

from accounts.decorators import admin_required, student_required
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BulkImportForm, DepartmentForm, StudentProfileForm
from .models import LEVEL_CHOICES, AdmissionRecord, Department, StudentProfile
from .services import create_student_account, seed_admission_record

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
                    with transaction.atomic():
                        for row in rows:
                            department = Department.objects.get(name__iexact=row["department"].strip())
                            optional_fields = {
                                field: row[field].strip()
                                for field in OPTIONAL_COLUMNS
                                if row.get(field, "").strip()
                            }
                            create_student_account(
                                matric_number=row["matric_number"],
                                first_name=row["first_name"].strip(),
                                last_name=row["last_name"].strip(),
                                email=row["email"].strip(),
                                department=department,
                                entry_level=int(row["level"]),
                                **optional_fields,
                            )
                    messages.success(request, f"Imported {len(rows)} students.")
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


def _validate_admission_row(row, seen_matrics, seen_emails):
    """Sibling of _validate_row, not a shared refactor - this one also checks against
    AdmissionRecord (so the same matric number can't be seeded twice) and against an
    existing StudentProfile (so an already-onboarded student doesn't get a redundant PIN),
    neither of which _validate_row needs to care about.
    """
    errors = []

    matric_number = (row.get("matric_number") or "").strip().upper()
    if not matric_number:
        errors.append("matric_number is required")
    elif matric_number in seen_matrics:
        errors.append(f"duplicate matric_number {matric_number} in file")
    elif StudentProfile.objects.filter(matric_number=matric_number).exists():
        errors.append(f"matric_number {matric_number} already has a full student account")
    elif AdmissionRecord.objects.filter(matric_number=matric_number).exists():
        errors.append(f"matric_number {matric_number} already has a pending admission record")
    else:
        seen_matrics.add(matric_number)

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif email in seen_emails:
        errors.append(f"duplicate email {email} in file")
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
def seed_admissions(request):
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
                for i, row in enumerate(rows, start=2):
                    for error in _validate_admission_row(row, seen_matrics, seen_emails):
                        errors.append(f"Row {i}: {error}")

                if errors:
                    for error in errors:
                        messages.error(request, error)
                else:
                    seeded = []
                    with transaction.atomic():
                        for row in rows:
                            department = Department.objects.get(name__iexact=row["department"].strip())
                            record, pin = seed_admission_record(
                                matric_number=row["matric_number"],
                                first_name=row["first_name"].strip(),
                                last_name=row["last_name"].strip(),
                                email=row["email"].strip(),
                                department=department,
                                entry_level=int(row["level"]),
                            )
                            seeded.append((record, pin))

                    # Emails go out AFTER the transaction commits - sending a batch of
                    # emails while holding a write lock open is expensive under SQLite's
                    # single-writer model, and a send_mail failure shouldn't roll back
                    # AdmissionRecords that are already correctly persisted.
                    failed_emails = []
                    for record, pin in seeded:
                        try:
                            send_mail(
                                subject="Your LU-SIMS registration details",
                                message=(
                                    f"Matric number: {record.matric_number}\n"
                                    f"PIN: {pin}\n\n"
                                    "Use these at the LU-SIMS login page (\"Is this your "
                                    "first time here?\") to complete your registration."
                                ),
                                from_email=None,
                                recipient_list=[record.email],
                            )
                        except Exception:
                            failed_emails.append(record.email)

                    messages.success(request, f"Seeded {len(seeded)} admission record(s).")
                    if failed_emails:
                        messages.warning(
                            request,
                            f"Could not send the PIN email to: {', '.join(failed_emails)}. "
                            "Follow up with them manually.",
                        )
                    return redirect("students:seed_admissions")
    else:
        form = BulkImportForm()

    return render(request, "students/seed_admissions.html", {"form": form})


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
