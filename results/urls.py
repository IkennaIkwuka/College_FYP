from django.urls import path

from . import views

app_name = "results"

urlpatterns = [
    path("courses/<int:pk>/", views.course_results_entry, name="course_results_entry"),
    path("my-results/", views.my_results, name="my_results"),
]
