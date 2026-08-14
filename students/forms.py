from accounts.forms import BootstrapFormMixin
from django import forms

from .models import Department, StudentProfile


class BulkImportForm(BootstrapFormMixin, forms.Form):
    csv_file = forms.FileField(label="CSV file")


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "hod"]


class StudentProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ["date_of_birth", "gender", "phone_number", "address"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}
