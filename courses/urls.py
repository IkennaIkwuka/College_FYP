from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("my-registrations/", views.my_registrations, name="my_registrations"),
    path("manage/", views.manage_courses, name="manage_courses"),
    path("manage/add/", views.course_add, name="course_add"),
    path("manage/<int:pk>/edit/", views.course_edit, name="course_edit"),
    path("manage/<int:pk>/toggle-active/", views.course_toggle_active, name="course_toggle_active"),
]
