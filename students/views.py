import csv
import io

from accounts.decorators import admin_required, registrar_required, student_required
from accounts.forms import PreferredUsernameForm
from accounts.services import force_password_reset
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import BulkImportForm, DepartmentForm, FacultyForm, StudentAccountForm, StudentEditForm, StudentProfileForm
from .models import ADMISSION_TYPE_CHOICES, LEVEL_CHOICES, Department, Faculty, StudentProfile, entry_level_choices_for
from .services import create_student_account, reset_student_pin, send_pin_email, sync_username_to_matric_number

REQUIRED_COLUMNS = {"matric_number", "first_name", "last_name", "email", "department", "level", "admission_type"}
OPTIONAL_COLUMNS = {"date_of_birth", "gender", "phone_number", "address"}
VALID_LEVELS = {str(level) for level, _ in LEVEL_CHOICES}

# Which entry levels the "level"/"entry_level" dropdown should offer for each admission
# type - drives the client-side restriction in register.html/student_form.html. The
# form's own clean() (students/forms.py) re-checks the same entry_level_choices_for()
# server-side, since this map only narrows the dropdown's options in the browser.
ENTRY_LEVEL_CHOICES_BY_ADMISSION_TYPE = {
    admission_type: entry_level_choices_for(admission_type) for admission_type, _ in ADMISSION_TYPE_CHOICES
}


@registrar_required
def register(request):
    if request.method == "POST":
        form = StudentAccountForm(request.POST)
        if form.is_valid():
            profile = create_student_account(
                matric_number=form.cleaned_data["matric_number"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                department=form.cleaned_data["department"],
                entry_level=form.cleaned_data["level"],
                admission_type=form.cleaned_data["admission_type"],
            )
            messages.success(
                request,
                f"Student {form.cleaned_data['matric_number']} added. "
                f'Their username is "{profile.user.username}"; '
                f'initial password is "{settings.DEFAULT_PASSWORD}". '
                "They'll request a verification code themselves at first login.",
            )
            return redirect("students:register")
    else:
        form = StudentAccountForm()

    return render(
        request,
        "students/register.html",
        {
            "form": form,
            "default_password": settings.DEFAULT_PASSWORD,
            "entry_level_choices_by_admission_type": ENTRY_LEVEL_CHOICES_BY_ADMISSION_TYPE,
        },
    )


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

    admission_type = (row.get("admission_type") or "").strip().upper()
    valid_admission_types = {code for code, _ in ADMISSION_TYPE_CHOICES}
    if admission_type not in valid_admission_types:
        errors.append(f"admission_type '{admission_type}' must be one of {sorted(valid_admission_types)}")

    level = (row.get("level") or "").strip()
    if level not in VALID_LEVELS:
        errors.append(f"level '{level}' must be one of {sorted(VALID_LEVELS)}")
    elif admission_type in valid_admission_types:
        # Same rule the interactive Add/Edit Student forms enforce - UTME is always
        # 100L, Direct Entry only 200L/300L, transfer unrestricted.
        allowed_levels = {str(value) for value, _ in entry_level_choices_for(admission_type)}
        if level not in allowed_levels:
            errors.append(
                f"level '{level}' is not valid for admission_type '{admission_type}' "
                f"(allowed: {sorted(allowed_levels)})"
            )

    return errors


@registrar_required
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
                                admission_type=row["admission_type"].strip().upper(),
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
            send_pin_email(profile, raw_pin)
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


def _filtered_student_profiles(request):
    query = request.GET.get("q", "").strip()
    department_id = request.GET.get("department", "").strip()
    level = request.GET.get("level", "").strip()
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
    if admission_type:
        profiles = profiles.filter(admission_type=admission_type)
    # current_level is derived (StudentProfile.current_level), not a DB field, so this
    # filter runs in Python rather than duplicating the entry-year/cap math into a
    # second ORM expression that could drift out of sync with the model property.
    if level:
        profiles = [profile for profile in profiles if profile.current_level == int(level)]
    return profiles, query, department_id, level, admission_type


@registrar_required
def manage_students(request):
    profiles, query, department_id, level, admission_type = _filtered_student_profiles(request)

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
            "selected_level": level,
            "selected_admission_type": admission_type,
        },
    )


@registrar_required
def student_search_suggestions(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        profiles, *_ = _filtered_student_profiles(request)
        for profile in profiles[:8]:
            results.append({
                "label": f"{profile.matric_number} — {profile.user.get_full_name() or profile.user.username}",
                "sublabel": profile.department.name if profile.department else "",
                "value": profile.matric_number,
                "url": reverse("students:student_detail", args=[profile.id]),
            })
    return JsonResponse({"results": results})


@registrar_required
def student_detail(request, pk):
    profile = get_object_or_404(StudentProfile.objects.select_related("user", "department"), pk=pk)
    return render(request, "students/student_detail.html", {"profile": profile})


@registrar_required
def student_edit(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)

    if request.method == "POST":
        form = StudentEditForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            if sync_username_to_matric_number(profile):
                messages.success(
                    request,
                    f"Updated {profile.matric_number}. Login username is now \"{profile.user.username}\".",
                )
            else:
                messages.success(request, f"Updated {profile.matric_number}.")
            return redirect("students:student_detail", pk=profile.id)
    else:
        form = StudentEditForm(instance=profile)

    return render(
        request,
        "students/student_form.html",
        {
            "form": form,
            "profile": profile,
            "entry_level_choices_by_admission_type": ENTRY_LEVEL_CHOICES_BY_ADMISSION_TYPE,
        },
    )


@student_required
def my_profile(request):
    profile = request.user.student_profile
    return render(request, "students/my_profile.html", {"profile": profile})


@student_required
def my_profile_edit(request):
    profile = request.user.student_profile

    if request.method == "POST" and "save_username" in request.POST:
        username_form = PreferredUsernameForm(request.POST, user=request.user)
        profile_form = StudentProfileForm(instance=profile)
        if username_form.is_valid():
            request.user.preferred_username = username_form.cleaned_data["preferred_username"]
            request.user.preferred_username_changed_at = timezone.now()
            request.user.save(update_fields=["preferred_username", "preferred_username_changed_at"])
            messages.success(request, "Preferred username updated.")
            return redirect("profile")
    elif request.method == "POST":
        profile_form = StudentProfileForm(request.POST, instance=profile)
        username_form = PreferredUsernameForm(user=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        profile_form = StudentProfileForm(instance=profile)
        username_form = PreferredUsernameForm(user=request.user)

    return render(
        request,
        "students/my_profile_edit.html",
        {"form": profile_form, "username_form": username_form, "profile": profile},
    )
