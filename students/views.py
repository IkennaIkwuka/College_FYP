import csv
import io

from accounts.decorators import admin_required
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import BulkImportForm
from .models import LEVEL_CHOICES, Department, StudentProfile
from .services import create_student_account

REQUIRED_COLUMNS = {"matric_number", "first_name", "last_name", "email", "department", "level"}
OPTIONAL_COLUMNS = {"date_of_birth", "gender", "phone_number", "address"}
VALID_LEVELS = {str(level) for level, _ in LEVEL_CHOICES}


def _validate_row(row, seen_matrics, seen_emails):
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
                for i, row in enumerate(rows, start=2):
                    for error in _validate_row(row, seen_matrics, seen_emails):
                        errors.append(f"Row {i}: {error}")

                if errors:
                    for error in errors:
                        messages.error(request, error)
                else:
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
                                level=int(row["level"]),
                                **optional_fields,
                            )
                    messages.success(request, f"Imported {len(rows)} students.")
                    return redirect("students:bulk_import")
    else:
        form = BulkImportForm()

    return render(request, "students/bulk_import.html", {"form": form})


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
