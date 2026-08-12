from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User
from .services import assign_staff_identity


class StaffAccountAddForm(forms.ModelForm):
    """The admin "add User" form, for staff accounts only.

    Deliberately has no username/password fields - because they're absent here,
    ModelForm._post_clean() skips validating them on instance.full_clean(), the same
    mechanism Django's own UserCreationForm relies on for its password fields. IT Admin
    fills in who the person is; assign_staff_identity() (called from save_model below)
    invents the username, staff_id and initial password. Not Bootstrap-styled - this
    form only ever renders inside Django admin's own theme, never a portal template.
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "groups")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Extends (not replaces) the stock fieldsets/list_display/list_filter - must_change_password
    # is what actually drives the forced first-login password change, but the default UserAdmin
    # has no idea it exists since it's a field this project added, not a stock Django one.
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Portal", {"fields": ("must_change_password", "staff_id")}),
    )
    list_display = BaseUserAdmin.list_display + ("staff_id", "must_change_password")
    list_filter = BaseUserAdmin.list_filter + ("must_change_password",)
    readonly_fields = BaseUserAdmin.readonly_fields + ("staff_id",)

    add_form = StaffAccountAddForm
    add_fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email", "groups")}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            assign_staff_identity(obj)
        super().save_model(request, obj, form, change)
        if not change:
            self.message_user(
                request,
                f'Staff account created. Username is "{obj.username}"; '
                f'initial password is "{settings.DEFAULT_PASSWORD}".',
            )


admin.site.site_header = "LU-SIMS Administration"
admin.site.site_title = "LU-SIMS Admin"
admin.site.index_title = "Administration"
