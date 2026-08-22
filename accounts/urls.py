from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("manage/staff/", views.manage_staff, name="manage_staff"),
    path("manage/staff/search/", views.staff_search_suggestions, name="staff_search_suggestions"),
    path("manage/staff/add/", views.staff_add, name="staff_add"),
    path("manage/staff/<int:pk>/edit/", views.staff_edit, name="staff_edit"),
    path(
        "manage/staff/<int:pk>/reset-password/",
        views.staff_force_password_reset,
        name="staff_force_password_reset",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("change-password/", views.ForcedPasswordChangeView.as_view(), name="change_password"),
    path("settings/change-password/", views.SelfChangePasswordView.as_view(), name="self_change_password"),
    path("settings/change-email/", views.request_email_change, name="request_email_change"),
    path("settings/change-email/verify/", views.confirm_email_change, name="confirm_email_change"),
    path("settings/change-email/resend/", views.resend_email_change_code, name="resend_email_change_code"),
    path("verify-pin/", views.verify_pin, name="verify_pin"),
    path("verify-pin/send-code/", views.send_pin_code, name="send_pin_code"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
    path("forgot-password/sent/", views.ForgotPasswordDoneView.as_view(), name="forgot_password_done"),
    path(
        "forgot-password/<uidb64>/<token>/",
        views.ForgotPasswordConfirmView.as_view(),
        name="forgot_password_confirm",
    ),
    path(
        "forgot-password/complete/",
        views.ForgotPasswordCompleteView.as_view(),
        name="forgot_password_complete",
    ),
]
