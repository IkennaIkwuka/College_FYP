from django.contrib import admin

from .models import Department, StudentProfile


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("matric_number", "user", "department", "level")
    list_filter = ("department", "level")
    search_fields = ("matric_number", "user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("department",)
