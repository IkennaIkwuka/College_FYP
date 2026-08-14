from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("manage/staff/", views.manage_staff, name="manage_staff"),
    path("manage/staff/add/", views.staff_add, name="staff_add"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("change-password/", views.ForcedPasswordChangeView.as_view(), name="change_password"),
]
