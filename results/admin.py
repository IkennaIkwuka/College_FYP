from django.contrib import admin

from .models import Result


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ["registration", "grade", "grade_point", "entered_by", "updated_at"]
    list_filter = ["grade"]
    search_fields = ["registration__student__matric_number", "registration__course__code"]
