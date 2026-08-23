from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from students.models import Department, Faculty, LEVEL_CHOICES

from accounts.decorators import dean_required, hod_required, lecturer_required, registrar_required, student_required

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
            existing_units = sum(
                r.course.units
                for r in profile.registrations.filter(session=session, semester=semester).select_related("course")
            )
            total_units = existing_units + sum(c.units for c in selected_courses)

            # NUC caps a semester's load at MAX_SEMESTER_UNITS - always enforced, since
            # exceeding it is never valid regardless of how registration is split across
            # visits.
            if total_units > settings.MAX_SEMESTER_UNITS:
                messages.error(
                    request,
                    f"Registering for these courses would bring your total to {total_units} "
                    f"units - the maximum allowed per semester is {settings.MAX_SEMESTER_UNITS}.",
                )
            else:
                for course in selected_courses:
                    registration = CourseRegistration(
                        student=profile, course=course, session=session, semester=semester
                    )
                    registration.full_clean()
                    registration.save()
                messages.success(request, f"Registered for {len(selected_courses)} course(s).")
                if total_units < settings.MIN_SEMESTER_UNITS:
                    messages.warning(
                        request,
                        f"You're now registered for {total_units} units this semester - the "
                        f"NUC minimum is {settings.MIN_SEMESTER_UNITS}. You may need to register "
                        "for more.",
                    )
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
    # Hard-filtered to the current semester, no override - a course sitting in a
    # semester that hasn't started yet has nothing actionable about it yet (no
    # exams run, nothing to enter results for), so it shouldn't be listed at all.
    courses = Course.objects.filter(lecturer=request.user, semester=settings.CURRENT_SEMESTER)
    return render(request, "courses/my_courses.html", {"courses": courses})


def _hod_department(request):
    # Group membership (hod_required) doesn't guarantee a Department actually points
    # at this user yet - that's a separate assignment, done via the Department admin.
    # Filtering rather than using the reverse OneToOneField accessor directly means a
    # missing assignment comes back as None instead of raising.
    return Department.objects.filter(hod=request.user).first()


def _dean_faculty(request):
    return Faculty.objects.filter(dean=request.user).first()


def _filtered_hod_courses(request, department):
    query = request.GET.get("q", "").strip()
    courses = Course.objects.filter(department=department).order_by("code")
    if query:
        courses = courses.filter(Q(code__icontains=query) | Q(title__icontains=query))
    selected_level = request.GET.get("level", "").strip()
    # No "semester" param at all means "just loaded the page" - default that case to
    # the current semester (matching how registration already works) rather than
    # showing every semester mixed together. An explicit ?semester= (including the
    # deliberate "All semesters" choice, which posts semester="") still overrides it.
    if "semester" in request.GET:
        selected_semester = request.GET.get("semester", "").strip()
    else:
        selected_semester = settings.CURRENT_SEMESTER
    selected_is_active = request.GET.get("is_active", "").strip()
    if selected_level:
        courses = courses.filter(level=selected_level)
    if selected_semester:
        courses = courses.filter(semester=selected_semester)
    if selected_is_active:
        courses = courses.filter(is_active=(selected_is_active == "1"))
    return courses, query, selected_level, selected_semester, selected_is_active


@hod_required
def manage_courses(request):
    department = _hod_department(request)
    courses = None
    querystring = ""
    query = selected_level = selected_semester = selected_is_active = ""
    if department:
        courses, query, selected_level, selected_semester, selected_is_active = _filtered_hod_courses(
            request, department
        )

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
            "query": query,
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
def course_search_suggestions(request):
    query = request.GET.get("q", "").strip()
    results = []
    department = _hod_department(request)
    if query and department:
        courses, *_ = _filtered_hod_courses(request, department)
        for course in courses[:8]:
            results.append({
                "label": f"{course.code} — {course.title}",
                "sublabel": department.name,
                "value": course.code,
                "url": reverse("courses:course_detail", args=[course.id]),
            })
    return JsonResponse({"results": results})


def _filtered_catalog_courses(request):
    query = request.GET.get("q", "").strip()
    courses = Course.objects.select_related("department", "lecturer").order_by("code")
    if query:
        courses = courses.filter(Q(code__icontains=query) | Q(title__icontains=query))

    selected_department = request.GET.get("department", "").strip()
    selected_level = request.GET.get("level", "").strip()
    selected_semester = request.GET.get("semester", "").strip()
    selected_is_active = request.GET.get("is_active", "").strip()
    if selected_department:
        courses = courses.filter(department_id=selected_department)
    if selected_level:
        courses = courses.filter(level=selected_level)
    if selected_semester:
        courses = courses.filter(semester=selected_semester)
    if selected_is_active:
        courses = courses.filter(is_active=(selected_is_active == "1"))
    return courses, query, selected_department, selected_level, selected_semester, selected_is_active


@registrar_required
def course_catalog(request):
    # View-only, university-wide - Registrar owns student/account records, not
    # course content, so this is deliberately not another course_add/edit surface.
    departments = Department.objects.all()
    courses, query, selected_department, selected_level, selected_semester, selected_is_active = (
        _filtered_catalog_courses(request)
    )

    paginator = Paginator(courses, 10)
    courses = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    return render(
        request,
        "courses/course_catalog.html",
        {
            "query": query,
            "courses": courses,
            "querystring": querystring,
            "departments": departments,
            "levels": LEVEL_CHOICES,
            "semesters": SEMESTER_CHOICES,
            "selected_department": selected_department,
            "selected_level": selected_level,
            "selected_semester": selected_semester,
            "selected_is_active": selected_is_active,
        },
    )


@registrar_required
def catalog_search_suggestions(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        courses, *_ = _filtered_catalog_courses(request)
        for course in courses[:8]:
            results.append({
                "label": f"{course.code} — {course.title}",
                "sublabel": course.department.name if course.department else "",
                "value": course.code,
                "url": None,
            })
    return JsonResponse({"results": results})


def _filtered_faculty_courses(request, faculty):
    query = request.GET.get("q", "").strip()
    courses = Course.objects.filter(department__faculty=faculty).select_related(
        "department", "lecturer"
    ).order_by("code")
    if query:
        courses = courses.filter(Q(code__icontains=query) | Q(title__icontains=query))

    selected_department = request.GET.get("department", "").strip()
    selected_level = request.GET.get("level", "").strip()
    selected_semester = request.GET.get("semester", "").strip()
    selected_is_active = request.GET.get("is_active", "").strip()
    if selected_department:
        courses = courses.filter(department_id=selected_department)
    if selected_level:
        courses = courses.filter(level=selected_level)
    if selected_semester:
        courses = courses.filter(semester=selected_semester)
    if selected_is_active:
        courses = courses.filter(is_active=(selected_is_active == "1"))
    return courses, query, selected_department, selected_level, selected_semester, selected_is_active


@dean_required
def faculty_courses(request):
    # View-only, scoped to the Dean's own faculty - same reasoning as course_catalog,
    # Dean oversees the faculty, HOD still owns each department's course content.
    faculty = _dean_faculty(request)
    courses = None
    departments = Department.objects.none()
    querystring = ""
    query = selected_department = selected_level = selected_semester = selected_is_active = ""
    if faculty:
        departments = Department.objects.filter(faculty=faculty)
        courses, query, selected_department, selected_level, selected_semester, selected_is_active = (
            _filtered_faculty_courses(request, faculty)
        )

        paginator = Paginator(courses, 10)
        courses = paginator.get_page(request.GET.get("page"))

        params = request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

    return render(
        request,
        "courses/faculty_courses.html",
        {
            "faculty": faculty,
            "query": query,
            "courses": courses,
            "querystring": querystring,
            "departments": departments,
            "levels": LEVEL_CHOICES,
            "semesters": SEMESTER_CHOICES,
            "selected_department": selected_department,
            "selected_level": selected_level,
            "selected_semester": selected_semester,
            "selected_is_active": selected_is_active,
        },
    )


@dean_required
def faculty_course_search_suggestions(request):
    query = request.GET.get("q", "").strip()
    results = []
    faculty = _dean_faculty(request)
    if query and faculty:
        courses, *_ = _filtered_faculty_courses(request, faculty)
        for course in courses[:8]:
            results.append({
                "label": f"{course.code} — {course.title}",
                "sublabel": course.department.name,
                "value": course.code,
                "url": None,
            })
    return JsonResponse({"results": results})


def _course_level_exceeds_duration(form, department):
    # Not something CourseForm can check itself - department isn't one of its
    # fields (it's assigned by the view, see course_add below), so the ceiling
    # has to be applied here, after is_valid() but before the course is saved.
    max_level = department.duration_years * 100
    level = form.cleaned_data.get("level")
    if level and int(level) > max_level:
        form.add_error(
            "level",
            f"{department} is a {department.duration_years}-year programme - course level "
            f"cannot exceed {max_level} Level.",
        )
        return True
    return False


@hod_required
def course_add(request):
    department = _hod_department(request)
    if department is None:
        messages.error(request, "You are not assigned as HOD of any department.")
        return redirect("courses:manage_courses")

    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid() and not _course_level_exceeds_duration(form, department):
            course = form.save(commit=False)
            course.department = department
            course.save()
            messages.success(request, f"Added {course.code}.")
            return redirect("courses:manage_courses")
    else:
        form = CourseForm()

    return render(request, "courses/course_form.html", {"form": form})


@hod_required
def course_detail(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)
    return render(request, "courses/course_detail.html", {"course": course})


@hod_required
def course_edit(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)

    if request.method == "POST":
        form = CourseForm(request.POST, instance=course)
        if form.is_valid() and not _course_level_exceeds_duration(form, department):
            form.save()
            messages.success(request, f"Updated {course.code}.")
            return redirect("courses:course_detail", pk=course.id)
    else:
        form = CourseForm(instance=course)

    return render(request, "courses/course_edit.html", {"form": form, "course": course})


def _filtered_registrations(request, course):
    query = request.GET.get("q", "").strip()
    registrations = course.registrations.select_related("student__user")
    if query:
        registrations = registrations.filter(
            Q(student__matric_number__icontains=query)
            | Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
            | Q(student__user__username__icontains=query)
        )

    selected_session = request.GET.get("session", "").strip()
    selected_semester = request.GET.get("semester", "").strip()
    if selected_session:
        registrations = registrations.filter(session=selected_session)
    if selected_semester:
        registrations = registrations.filter(semester=selected_semester)
    registrations = registrations.order_by("-session", "semester")
    return registrations, query, selected_session, selected_semester


@hod_required
def course_registrations(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)
    registrations, query, selected_session, selected_semester = _filtered_registrations(request, course)

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
            "query": query,
            "registrations": registrations,
            "querystring": querystring,
            "sessions": sessions,
            "semesters": SEMESTER_CHOICES,
            "selected_session": selected_session,
            "selected_semester": selected_semester,
        },
    )


@hod_required
def registration_search_suggestions(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        registrations, *_ = _filtered_registrations(request, course)
        for registration in registrations[:8]:
            student = registration.student
            results.append({
                "label": student.user.get_full_name() or student.user.username,
                "sublabel": student.matric_number,
                "value": student.matric_number,
                "url": None,
            })
    return JsonResponse({"results": results})


@hod_required
def course_toggle_active(request, pk):
    department = _hod_department(request)
    course = get_object_or_404(Course, pk=pk, department=department)

    if request.method == "POST":
        course.is_active = not course.is_active
        course.save(update_fields=["is_active"])
        messages.success(request, f"{course.code} is now {'active' if course.is_active else 'inactive'}.")
    return redirect("courses:manage_courses")
