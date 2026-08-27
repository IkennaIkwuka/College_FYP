from audit.models import AuditLog
from audit.services import log_action
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import student_required
from courses.models import Course
from students.models import Department

from .forms import ScoreEntryFormSet
from .models import Result
from .services import compute_cgpa, compute_gpa, degree_classification


def _hod_department(request):
    # Same reasoning as courses/views.py::_hod_department - group membership alone
    # doesn't guarantee a Department actually points back at this user.
    return Department.objects.filter(hod=request.user).first()


def _department_hod_for(request, course):
    """Returns the Department if request.user HODs the course's own department, else None."""
    if not request.user.is_hod:
        return None
    department = _hod_department(request)
    if department is not None and course.department_id == department.id:
        return department
    return None


def _is_owning_lecturer(request, course):
    return request.user.is_lecturer and course.lecturer_id == request.user.id


@login_required
def course_results_entry(request, pk):
    course = get_object_or_404(Course, pk=pk)
    is_hod_here = _department_hod_for(request, course) is not None
    is_owning_lecturer = _is_owning_lecturer(request, course)
    if not (is_hod_here or is_owning_lecturer):
        raise PermissionDenied("You are not authorized to enter results for this course.")

    # A course sitting in a semester that isn't the current one hasn't happened yet -
    # no exams run, nothing offline to have approved, so nothing here is enterable for
    # anyone yet. My Courses/Manage Courses already hide these by default, but this is
    # the actual enforcement point (an HOD's explicit "All semesters" filter, or a
    # stale/bookmarked link, could still reach this URL directly).
    is_current_semester = course.semester == settings.CURRENT_SEMESTER

    sessions = list(course.registrations.values_list("session", flat=True).distinct().order_by("-session"))
    if settings.CURRENT_SESSION not in sessions:
        sessions.insert(0, settings.CURRENT_SESSION)
    session = request.GET.get("session") or settings.CURRENT_SESSION

    roster = list(
        course.registrations.filter(session=session)
        .select_related("student__user", "result")
        .order_by("student__matric_number")
    )

    if request.method == "POST" and not is_current_semester:
        messages.error(request, "Results entry is only open for the current semester's courses.")
        return redirect(f"{request.path}?session={session}")

    roster_by_id = {r.id: r for r in roster}

    if request.method == "POST":
        formset = ScoreEntryFormSet(request.POST)
        if formset.is_valid():
            updated = 0
            locked = 0
            for form_data in formset.cleaned_data:
                score = form_data.get("score")
                if score is None:
                    continue
                registration_id = form_data["registration_id"]
                # Once a Lecturer's initial score is in, only the HOD can touch it again -
                # mirrors the real "forwarded to HOD" step, where the copy is out of the
                # lecturer's hands. Re-checked here, not just hidden in the template, since
                # a crafted POST could otherwise bypass a purely client-side lock.
                if Result.objects.filter(registration_id=registration_id).exists() and not is_hod_here:
                    locked += 1
                    continue
                obj, created = Result.objects.update_or_create(
                    registration_id=registration_id,
                    defaults={"score": score, "entered_by": request.user},
                )
                registration = roster_by_id[registration_id]
                log_action(
                    action=AuditLog.CREATE if created else AuditLog.UPDATE,
                    actor=request.user,
                    target_description=f"Result {registration.student.matric_number} - {course.code} ({session})",
                    request=request,
                )
                updated += 1
            if locked:
                messages.warning(
                    request, f"{locked} result(s) already entered - only the HOD can correct an existing score."
                )
            if updated:
                messages.success(request, f"Saved {updated} result(s).")
            return redirect(f"{request.path}?session={session}")
    else:
        initial = [
            {
                "registration_id": registration.id,
                "score": registration.result.score if hasattr(registration, "result") else None,
            }
            for registration in roster
        ]
        formset = ScoreEntryFormSet(initial=initial)

    rows = []
    for registration, form in zip(roster, formset.forms):
        has_result = hasattr(registration, "result")
        if not is_current_semester:
            locked, locked_reason = True, "semester"
        elif has_result and not is_hod_here:
            locked, locked_reason = True, "hod_only"
        else:
            locked, locked_reason = False, None
        rows.append(
            {"registration": registration, "form": form, "locked": locked, "locked_reason": locked_reason}
        )

    return render(
        request,
        "results/course_results_entry.html",
        {
            "course": course,
            "formset": formset,
            "rows": rows,
            "sessions": sessions,
            "session": session,
            "is_hod_here": is_hod_here,
            "is_current_semester": is_current_semester,
        },
    )


@student_required
def my_results(request):
    profile = request.user.student_profile
    results = (
        Result.objects.filter(registration__student=profile)
        .select_related("registration__course")
        .order_by("-registration__session", "registration__semester")
    )

    groups = {}
    for result in results:
        key = (result.registration.session, result.registration.semester)
        groups.setdefault(key, []).append(result)

    semesters = [
        {
            "session": session,
            "semester": semester,
            "results": group_results,
            "gpa": compute_gpa(Result.objects.filter(id__in=[r.id for r in group_results])),
        }
        for (session, semester), group_results in groups.items()
    ]

    cgpa = compute_cgpa(profile)

    return render(
        request,
        "results/my_results.html",
        {
            "semesters": semesters,
            "cgpa": cgpa,
            "classification": degree_classification(cgpa),
        },
    )
