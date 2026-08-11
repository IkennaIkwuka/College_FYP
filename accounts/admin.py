from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Extends (not replaces) the stock fieldsets/list_display/list_filter - must_change_password
    # is what actually drives the forced first-login password change, but the default UserAdmin
    # has no idea it exists since it's a field this project added, not a stock Django one.
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Portal", {"fields": ("must_change_password",)}),
    )
    list_display = BaseUserAdmin.list_display + ("must_change_password",)
    list_filter = BaseUserAdmin.list_filter + ("must_change_password",)


admin.site.site_header = "LU-SIMS Administration"
admin.site.site_title = "LU-SIMS Admin"
admin.site.index_title = "Administration"
