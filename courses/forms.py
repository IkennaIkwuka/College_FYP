from django import forms

from accounts.forms import BootstrapFormMixin
from lu_sims.id_format import InvalidAcademicID, format_course_code

from .models import Course


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    # department is deliberately excluded - the view sets it from the HOD's own
    # department, so a course can never be created/reassigned outside it via form data.
    class Meta:
        model = Course
        fields = ["code", "title", "units", "level", "semester", "lecturer", "is_active"]

    def clean(self):
        # Needs code, level, and semester together (to cross-check the code's
        # leading digit against the level and trailing digit against the semester),
        # so this has to be the whole-form clean() - clean_code() alone can't rely
        # on the other fields already being in cleaned_data.
        cleaned_data = super().clean()
        code = cleaned_data.get("code")
        level = cleaned_data.get("level")
        semester = cleaned_data.get("semester")
        if code and level and semester:
            try:
                cleaned_data["code"] = format_course_code(code, int(level), semester)
            except InvalidAcademicID as e:
                self.add_error("code", str(e))
        return cleaned_data


class CourseSelectionForm(forms.Form):
    # Left off BootstrapFormMixin deliberately - it stamps "form-control" on every
    # widget, but a CheckboxSelectMultiple needs Bootstrap's "form-check-input"
    # class instead, which the template applies directly to each checkbox.
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    def __init__(self, *args, queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courses"].queryset = queryset
