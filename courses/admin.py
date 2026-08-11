from django.contrib import admin

from .models import Course, CourseRegistration


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department", "level", "semester", "units", "lecturer", "is_active")
    list_filter = ("department", "level", "semester", "is_active")
    search_fields = ("code", "title")
    autocomplete_fields = ("department", "lecturer")


@admin.register(CourseRegistration)
class CourseRegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "session", "semester", "registered_at")
    list_filter = ("session", "semester", "course__department")
    search_fields = ("student__matric_number", "course__code")
    autocomplete_fields = ("student", "course")
