from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("change-password/", views.ForcedPasswordChangeView.as_view(), name="change_password"),
    path("register/self/", views.self_register_matric, name="self_register_start"),
    path("register/self/pin/", views.self_register_pin, name="self_register_pin"),
    path("register/self/password/", views.self_register_password, name="self_register_password"),
]
