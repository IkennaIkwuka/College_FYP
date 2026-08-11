from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Course


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    # department is deliberately excluded - the view sets it from the HOD's own
    # department, so a course can never be created/reassigned outside it via form data.
    class Meta:
        model = Course
        fields = ["code", "title", "units", "level", "semester", "lecturer", "is_active"]


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
