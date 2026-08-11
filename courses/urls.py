from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("my-registrations/", views.my_registrations, name="my_registrations"),
]
