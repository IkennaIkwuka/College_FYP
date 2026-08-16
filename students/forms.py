from accounts.forms import BootstrapFormMixin
from django import forms

from .models import Department, Faculty, StudentProfile


class BulkImportForm(BootstrapFormMixin, forms.Form):
    csv_file = forms.FileField(label="CSV file")


class FacultyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ["name", "dean"]


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "faculty", "hod"]


class StudentProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ["date_of_birth", "gender", "phone_number", "address"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}


class StudentEditForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            "matric_number",
            "department",
            "entry_level",
            "admission_type",
            "date_of_birth",
            "gender",
            "phone_number",
            "address",
        ]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}
