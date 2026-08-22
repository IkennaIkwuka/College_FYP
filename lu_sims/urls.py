"""
URL configuration for lu_sims project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from accounts import views as accounts_views
from django.contrib import admin
from django.urls import include, path

from . import views as lu_sims_views

urlpatterns = [
    path('login/', accounts_views.PortalLoginView.as_view(), name='login'),
    path('profile/', lu_sims_views.profile, name='profile'),
    path('profile/edit/', lu_sims_views.profile_edit, name='profile_edit'),
    path('dashboard/', accounts_views.dashboard, name='dashboard'),
    path('dashboard/admin/', accounts_views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/dean/', accounts_views.dean_dashboard, name='dean_dashboard'),
    path('dashboard/hod/', accounts_views.hod_dashboard, name='hod_dashboard'),
    path('dashboard/registrar/', accounts_views.registrar_dashboard, name='registrar_dashboard'),
    path('dashboard/bursar/', accounts_views.bursar_dashboard, name='bursar_dashboard'),
    path('dashboard/lecturer/', accounts_views.lecturer_dashboard, name='lecturer_dashboard'),
    path('dashboard/student/', accounts_views.student_dashboard, name='student_dashboard'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('students/', include('students.urls')),
    path('courses/', include('courses.urls')),
]
