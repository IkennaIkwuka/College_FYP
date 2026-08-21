from accounts.forms import BootstrapFormMixin
from accounts.models import User
from django import forms
from lu_sims.id_format import InvalidAcademicID, format_academic_id

from .models import ADMISSION_TYPE_CHOICES, LEVEL_CHOICES, Department, Faculty, StudentProfile


class StudentAccountForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    matric_number = forms.CharField(max_length=20)
    department = forms.ModelChoiceField(queryset=Department.objects.all())
    level = forms.ChoiceField(choices=LEVEL_CHOICES)
    admission_type = forms.ChoiceField(choices=ADMISSION_TYPE_CHOICES)

    def clean_matric_number(self):
        try:
            matric_number = format_academic_id(self.cleaned_data["matric_number"])
        except InvalidAcademicID as e:
            raise forms.ValidationError(str(e))
        if StudentProfile.objects.filter(matric_number=matric_number).exists():
            raise forms.ValidationError("A student with this matric number already exists.")
        return matric_number

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


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
    # Not part of StudentProfile - these live on the related User instead, so they
    # can't come from Meta.fields like the rest. __init__/save() below wire them to
    # profile.user, matching how StudentAccountForm (creation) already asks for them.
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
        # Purely cosmetic - puts identity fields first instead of wherever Django's
        # ModelForm machinery would otherwise append declared-but-not-in-Meta fields.
        self.order_fields(
            ["first_name", "last_name", "email", "matric_number", "department",
             "entry_level", "admission_type", "date_of_birth", "gender", "phone_number", "address"]
        )

    def clean_matric_number(self):
        try:
            matric_number = format_academic_id(self.cleaned_data["matric_number"])
        except InvalidAcademicID as e:
            raise forms.ValidationError(str(e))
        if StudentProfile.objects.exclude(pk=self.instance.pk).filter(matric_number=matric_number).exists():
            raise forms.ValidationError("A student with this matric number already exists.")
        return matric_number

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.exclude(pk=self.instance.user_id).filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.first_name = self.cleaned_data["first_name"]
        profile.user.last_name = self.cleaned_data["last_name"]
        profile.user.email = self.cleaned_data["email"]
        if commit:
            profile.user.save(update_fields=["first_name", "last_name", "email"])
            profile.save()
        return profile
