from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.decorators import student_required

from .forms import CourseSelectionForm, SemesterForm
from .models import Course, CourseRegistration


@student_required
def register(request):
    profile = request.user.student_profile

    # Step 1: the semester form uses GET, so a submission lands back on this same
    # view with "?semester=..." already in the query string - no separate redirect
    # needed, the form's own field name doubles as step 2's input. Session isn't
    # asked for - it's just the current academic session (no carryover support yet).
    semester_form = SemesterForm(request.GET or None)
    if not semester_form.is_bound or not semester_form.is_valid():
        return render(request, "courses/select_semester.html", {"form": semester_form})

    session = settings.CURRENT_SESSION
    semester = semester_form.cleaned_data["semester"]

    # Step 2: session/semester picked - narrow courses to the student's own
    # department/level (CourseRegistration.clean() would reject anything else
    # anyway) and drop ones already registered for this session/semester.
    already_registered = profile.registrations.filter(session=session, semester=semester).values_list(
        "course_id", flat=True
    )
    available_courses = Course.objects.filter(
        department=profile.department, level=profile.level, semester=semester
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

    return render(
        request,
        "courses/select_courses.html",
        {"form": form, "session": session, "semester": semester},
    )


@student_required
def my_registrations(request):
    profile = request.user.student_profile
    registrations = profile.registrations.select_related("course").order_by("-session", "semester")
    return render(request, "courses/my_registrations.html", {"registrations": registrations})
