from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from students.services import create_student_account

from .decorators import admin_required
from .forms import ChangePasswordForm, StudentAccountForm


@admin_required
def register(request):
    if request.method == "POST":
        form = StudentAccountForm(request.POST)
        if form.is_valid():
            create_student_account(
                matric_number=form.cleaned_data["matric_number"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
                department=form.cleaned_data["department"],
                level=form.cleaned_data["level"],
            )
            messages.success(
                request,
                f"Student {form.cleaned_data['matric_number']} added. "
                f"Their initial password is \"{settings.DEFAULT_STUDENT_PASSWORD}\".",
            )
            return redirect("accounts:register")
    else:
        form = StudentAccountForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form, "default_password": settings.DEFAULT_STUDENT_PASSWORD},
    )


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html")


class ForcedPasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/change_password.html"
    form_class = ChangePasswordForm
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=["must_change_password"])
        messages.success(self.request, "Password changed.")
        return response
