from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from students.models import LEVEL_CHOICES

from accounts.decorators import student_required

from .forms import CourseSelectionForm
from .models import Course, CourseRegistration


@student_required
def register(request):
    profile = request.user.student_profile
    session = settings.CURRENT_SESSION
    semester = settings.CURRENT_SEMESTER

    # Session and semester both come from settings, not the student - narrow courses
    # to the student's own department, the fixed current semester, and anything at or
    # below their current level (lets a student pick up an earlier-level course they
    # fell behind on, alongside their own-level courses, in the same pass). The upper
    # bound (nothing above current level) is still enforced - see CourseRegistration.clean().
    already_registered = profile.registrations.filter(session=session, semester=semester).values_list(
        "course_id", flat=True
    )
    available_courses = Course.objects.filter(
        department=profile.department, level__lte=profile.current_level, semester=semester
    ).exclude(id__in=already_registered)

    if request.method == "POST":
        form = CourseSelectionForm(request.POST, queryset=available_courses)
        if form.is_valid():
            selected_courses = form.cleaned_data["courses"]
            for course in selected_courses:
                registration = CourseRegistration(
                    student=profile, course=course, session=session, semester=semester
                )
                registration.full_clean()
                registration.save()
            messages.success(request, f"Registered for {len(selected_courses)} course(s).")
            return redirect("courses:my_registrations")
    else:
        form = CourseSelectionForm(queryset=available_courses)

    # Grouped by year for the template - one collapsible section per level, rather
    # than one long flat checkbox list mixing every level together.
    courses_by_level = [
        (level, level // 100, [c for c in available_courses if c.level == level])
        for level, _ in LEVEL_CHOICES
    ]
    courses_by_level = [group for group in courses_by_level if group[2]]

    return render(
        request,
        "courses/register.html",
        {
            "form": form,
            "session": session,
            "semester": semester,
            "courses_by_level": courses_by_level,
            "current_level": profile.current_level,
        },
    )


@student_required
def my_registrations(request):
    profile = request.user.student_profile
    registrations = profile.registrations.select_related("course").order_by("-session", "semester")
    return render(request, "courses/my_registrations.html", {"registrations": registrations})
