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


def _can_enter_results_for(request, course):
    if request.user.is_lecturer and course.lecturer_id == request.user.id:
        return True
    if request.user.is_hod:
        department = _hod_department(request)
        if department is not None and course.department_id == department.id:
            return True
    return False


@login_required
def course_results_entry(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if not _can_enter_results_for(request, course):
        raise PermissionDenied("You are not authorized to enter results for this course.")

    sessions = list(course.registrations.values_list("session", flat=True).distinct().order_by("-session"))
    if settings.CURRENT_SESSION not in sessions:
        sessions.insert(0, settings.CURRENT_SESSION)
    session = request.GET.get("session") or settings.CURRENT_SESSION

    roster = list(
        course.registrations.filter(session=session)
        .select_related("student__user", "result")
        .order_by("student__matric_number")
    )

    if request.method == "POST":
        formset = ScoreEntryFormSet(request.POST)
        if formset.is_valid():
            updated = 0
            for form_data in formset.cleaned_data:
                score = form_data.get("score")
                if score is None:
                    continue
                Result.objects.update_or_create(
                    registration_id=form_data["registration_id"],
                    defaults={"score": score, "entered_by": request.user},
                )
                updated += 1
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

    rows = list(zip(roster, formset.forms))

    return render(
        request,
        "results/course_results_entry.html",
        {
            "course": course,
            "formset": formset,
            "rows": rows,
            "sessions": sessions,
            "session": session,
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
