from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import STAFF_GROUPS
from .models import User
from .services import assign_staff_identity, generate_staff_id


class StaffAccountAddForm(forms.ModelForm):
    """The admin "add User" form, for staff accounts only.

    Deliberately has no username/password fields - because they're absent here,
    ModelForm._post_clean() skips validating them on instance.full_clean(), the same
    mechanism Django's own UserCreationForm relies on for its password fields. IT Admin
    fills in who the person is and picks their role; assign_staff_identity() (called
    from save_model below) generates the staff_id/username and invents the initial
    password. Not Bootstrap-styled - this form only ever renders inside Django admin's
    own theme, never a portal template.
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "groups")

    def clean_groups(self):
        groups = self.cleaned_data["groups"]
        staff_groups = [g for g in groups if g.name in STAFF_GROUPS]
        if len(staff_groups) != 1:
            raise forms.ValidationError("Select exactly one staff role.")
        return groups


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

    add_form = StaffAccountAddForm
    add_fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email", "groups")}),
    )

    def get_readonly_fields(self, request, obj=None):
        # staff_id is system-generated at creation time, then locked - changing it later
        # would desync from the username, which is already derived and fixed by then.
        readonly = super().get_readonly_fields(request, obj)
        if obj is not None:
            readonly = tuple(readonly) + ("staff_id",)
        return readonly

    def save_model(self, request, obj, form, change):
        if not change:
            group = next(g for g in form.cleaned_data["groups"] if g.name in STAFF_GROUPS)
            obj.staff_id = generate_staff_id(group)
            assign_staff_identity(obj)
        super().save_model(request, obj, form, change)
        if not change:
            self.message_user(
                request,
                f'Staff account created. Username is "{obj.username}". Django admin has '
                "no setup-link button - go to Manage Staff in the portal to invite them.",
            )


admin.site.site_header = "LU-SIMS Administration"
admin.site.site_title = "LU-SIMS Admin"
admin.site.index_title = "Administration"
