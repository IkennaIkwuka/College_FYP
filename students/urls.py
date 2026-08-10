from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("import/", views.bulk_import, name="bulk_import"),
    path("lookup/", views.lookup, name="lookup"),
]
