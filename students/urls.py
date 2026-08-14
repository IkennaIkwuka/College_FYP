from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("import/", views.bulk_import, name="bulk_import"),
    path("lookup/", views.lookup, name="lookup"),
    path("seed-admissions/", views.seed_admissions, name="seed_admissions"),
    path("manage/departments/", views.manage_departments, name="manage_departments"),
    path("manage/departments/add/", views.department_add, name="department_add"),
    path("manage/departments/<int:pk>/edit/", views.department_edit, name="department_edit"),
    path("my-profile/", views.my_profile, name="my_profile"),
]
