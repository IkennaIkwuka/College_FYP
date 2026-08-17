from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("my-registrations/", views.my_registrations, name="my_registrations"),
    path("my-courses/", views.my_courses, name="my_courses"),
    path("manage/", views.manage_courses, name="manage_courses"),
    path("manage/search/", views.course_search_suggestions, name="course_search_suggestions"),
    path("manage/add/", views.course_add, name="course_add"),
    path("manage/<int:pk>/edit/", views.course_edit, name="course_edit"),
    path("manage/<int:pk>/registrations/", views.course_registrations, name="course_registrations"),
    path(
        "manage/<int:pk>/registrations/search/",
        views.registration_search_suggestions,
        name="registration_search_suggestions",
    ),
    path("manage/<int:pk>/toggle-active/", views.course_toggle_active, name="course_toggle_active"),
    path("catalog/", views.course_catalog, name="course_catalog"),
    path("catalog/search/", views.catalog_search_suggestions, name="catalog_search_suggestions"),
    path("faculty/", views.faculty_courses, name="faculty_courses"),
    path("faculty/search/", views.faculty_course_search_suggestions, name="faculty_course_search_suggestions"),
]
