from django.contrib import admin

from .models import Department, Faculty, StudentProfile


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "dean")
    search_fields = ("name",)
    autocomplete_fields = ("dean",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty", "hod")
    search_fields = ("name",)
    autocomplete_fields = ("faculty", "hod")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("matric_number", "user", "department", "entry_level", "current_level_display", "admission_type")
    list_filter = ("department", "entry_level", "admission_type")
    search_fields = ("matric_number", "user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("department",)

    @admin.display(description="Current level")
    def current_level_display(self, obj):
        return obj.current_level_display
