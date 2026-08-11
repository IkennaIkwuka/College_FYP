from django import forms

from .models import Course


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
