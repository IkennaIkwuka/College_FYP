from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from students.models import Department, LEVEL_CHOICES

from accounts.decorators import hod_required, lecturer_required, student_required

from .forms import CourseForm, CourseSelectionForm
from .models import SEMESTER_CHOICES, Course, CourseRegistration


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
        department=profile.department, level__lte=profile.current_level, semester=semester, is_active=True
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


@lecturer_required
def my_courses(request):
    courses = Course.objects.filter(lecturer=request.user)
    return render(request, "courses/my_courses.html", {"courses": courses})


def _hod_department(request):
    # Group membership (hod_required) doesn't guarantee a Department actually points
    # at this user yet - that's a separate assignment, done via the Department admin.
    # Filtering rather than using the reverse OneToOneField accessor directly means a
    # missing assignment comes back as None instead of raising.
    return Department.objects.filter(hod=request.user).first()


@hod_required
def manage_courses(request):
    department = _hod_department(request)
    courses = None
    querystring = ""
    selected_level = selected_semester = selected_is_active = ""
    if department:
        courses = Course.objects.filter(department=department).order_by("code")
        selected_level = request.GET.get("level", "").strip()
        selected_semester = request.GET.get("semester", "").strip()
        selected_is_active = request.GET.get("is_active", "").strip()
        if selected_level:
            courses = courses.filter(level=selected_level)
        if selected_semester:
            courses = courses.filter(semester=selected_semester)
        if selected_is_active:
            courses = courses.filter(is_active=(selected_is_active == "1"))

        paginator = Paginator(courses, 10)
        courses = paginator.get_page(request.GET.get("page"))

        params = request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

    return render(
        request,
        "courses/manage_courses.html",
        {
            "department": department,
            "courses": courses,
            "querystring": querystring,
            "levels": LEVEL_CHOICES,
            "semesters": SEMESTER_CHOICES,
            "selected_level": selected_level,
            "selected_semester": selected_semester,
            "selected_is_active": selected_is_active,
        },
    )


@hod_required
def course_add(request):
    department = _hod_department(request)
    if department is None:
        messages.error(request, "You are not assigned as HOD of any department.")
        return redirect("courses:manage_courses")

    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.department = department
            course.save()
            messages.success(request, f"Added {course.code}.")
            return redirect("courses:manage_courses")
    else:
        form = CourseForm()

    return render(request, "courses/course_form.html", {"form": form, "title": "Add Course"})


@hod_required
def course_edit(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)

    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {course.code}.")
            return redirect("courses:manage_courses")
    else:
        form = CourseForm(instance=course)

    return render(request, "courses/course_form.html", {"form": form, "title": f"Edit {course.code}"})


@hod_required
def course_registrations(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)
    registrations = course.registrations.select_related("student__user")

    selected_session = request.GET.get("session", "").strip()
    selected_semester = request.GET.get("semester", "").strip()
    if selected_session:
        registrations = registrations.filter(session=selected_session)
    if selected_semester:
        registrations = registrations.filter(semester=selected_semester)
    registrations = registrations.order_by("-session", "semester")

    sessions = course.registrations.values_list("session", flat=True).distinct().order_by("-session")

    paginator = Paginator(registrations, 10)
    registrations = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    return render(
        request,
        "courses/course_registrations.html",
        {
            "course": course,
            "registrations": registrations,
            "querystring": querystring,
            "sessions": sessions,
            "semesters": SEMESTER_CHOICES,
            "selected_session": selected_session,
            "selected_semester": selected_semester,
        },
    )


@hod_required
def course_toggle_active(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)

    if request.method == "POST":
        course.is_active = not course.is_active
        course.save(update_fields=["is_active"])
        messages.success(request, f"{course.code} is now {'active' if course.is_active else 'inactive'}.")
    return redirect("courses:manage_courses")
