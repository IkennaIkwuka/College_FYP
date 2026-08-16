from accounts.forms import BootstrapFormMixin
from django import forms
from lu_sims.id_format import InvalidAcademicID, format_academic_id

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
        fields = ["name", "faculty", "hod", "duration_years"]


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

    def clean_matric_number(self):
        try:
            matric_number = format_academic_id(self.cleaned_data["matric_number"])
        except InvalidAcademicID as e:
            raise forms.ValidationError(str(e))
        if StudentProfile.objects.exclude(pk=self.instance.pk).filter(matric_number=matric_number).exists():
            raise forms.ValidationError("A student with this matric number already exists.")
        return matric_number
