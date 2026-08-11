from django import forms

from accounts.forms import BootstrapFormMixin

from .models import SEMESTER_CHOICES, Course


class SessionSemesterForm(BootstrapFormMixin, forms.Form):
    session = forms.CharField(max_length=9, help_text="e.g. 2025/2026")
    semester = forms.ChoiceField(choices=SEMESTER_CHOICES)

    def clean_session(self):
        return self.cleaned_data["session"].strip()


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
