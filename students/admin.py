from django.contrib import admin

from .models import AdmissionRecord, Department, StudentProfile


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "hod")
    search_fields = ("name",)
    autocomplete_fields = ("hod",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("matric_number", "user", "department", "entry_level", "current_level_display")
    list_filter = ("department", "entry_level")
    search_fields = ("matric_number", "user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("department",)

    @admin.display(description="Current level")
    def current_level_display(self, obj):
        return obj.current_level_display


@admin.register(AdmissionRecord)
class AdmissionRecordAdmin(admin.ModelAdmin):
    list_display = (
        "matric_number", "first_name", "last_name", "email",
        "department", "entry_level", "failed_attempts", "locked_status",
    )
    list_filter = ("department", "entry_level")
    search_fields = ("matric_number", "first_name", "last_name", "email")
    autocomplete_fields = ("department",)
    exclude = ("pin_hash",)
    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        # The only creation path is students:seed_admissions, which generates a real PIN -
        # a manually-added record here would have no working pin_hash at all.
        return False

    @admin.display(description="Locked?", boolean=True)
    def locked_status(self, obj):
        return obj.is_locked
