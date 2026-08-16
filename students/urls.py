from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("import/", views.bulk_import, name="bulk_import"),
    path("lookup/", views.lookup, name="lookup"),
    path("manage/faculties/", views.manage_faculties, name="manage_faculties"),
    path("manage/faculties/add/", views.faculty_add, name="faculty_add"),
    path("manage/faculties/<int:pk>/edit/", views.faculty_edit, name="faculty_edit"),
    path("manage/departments/", views.manage_departments, name="manage_departments"),
    path("manage/departments/add/", views.department_add, name="department_add"),
    path("manage/departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
    path("manage/students/", views.manage_students, name="manage_students"),
    path("manage/students/<int:pk>/edit/", views.student_edit, name="student_edit"),
    path("my-profile/", views.my_profile, name="my_profile"),
]
