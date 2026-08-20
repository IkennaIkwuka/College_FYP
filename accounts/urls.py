from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
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
    path("verify-pin/", views.verify_pin, name="verify_pin"),
    path("verify-pin/send-code/", views.send_pin_code, name="send_pin_code"),
]
