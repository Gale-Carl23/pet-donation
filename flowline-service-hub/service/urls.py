from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("overview/", views.dashboard, name="dashboard"),
    path("schedule/", views.schedule, name="schedule"),
    path("field/", views.field, name="field"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/save/", views.job_save, name="job_save"),
    path("jobs/<int:pk>/assign/", views.job_assign, name="job_assign"),
    path("jobs/<int:pk>/cancel/", views.job_cancel, name="job_cancel"),
    path("customers/", views.customers, name="customers"),
    path("customers/new/", views.customer_form, name="customer_new"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customer_form, name="customer_edit"),
    path("customers/<int:pk>/archive/", views.customer_archive, name="customer_archive"),
    path("customers/<int:customer_id>/systems/new/", views.system_new, name="system_new"),
    path("customers/<int:customer_id>/book/", views.job_new, name="job_new_customer"),
    path("systems/<int:pk>/", views.system_detail, name="system_detail"),
    path("systems/<int:pk>/archive/", views.system_archive, name="system_archive"),
    path("systems/<int:pk>/reminder/", views.reminder, name="reminder"),
    path("systems/<int:system_id>/book/", views.job_new, name="job_new"),
    path("settings/", views.company_settings, name="company_settings"),
    path("settings/audit/", views.audit_log, name="audit_log"),
]
