from django.contrib import admin

from .models import AuditLog, CompanySettings, Component, Customer, Job, JobTask, WaterSystem


class ComponentInline(admin.TabularInline):
    model = Component
    extra = 0


class JobTaskInline(admin.TabularInline):
    model = JobTask
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "customer_type", "area", "contact_name", "phone", "is_active")
    list_filter = ("customer_type", "is_active")
    search_fields = ("name", "area", "contact_name", "phone")


@admin.register(WaterSystem)
class WaterSystemAdmin(admin.ModelAdmin):
    list_display = ("customer", "system_type", "label", "serial", "install_date", "is_active")
    list_filter = ("system_type", "is_active")
    search_fields = ("customer__name", "serial", "model")
    inlines = [ComponentInline]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("scheduled_date", "customer", "job_type", "technician", "status")
    list_filter = ("status", "job_type", "technician")
    search_fields = ("customer__name",)
    date_hierarchy = "scheduled_date"
    inlines = [JobTaskInline]


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: audit entries can't be edited or deleted from the admin."""

    list_display = ("at", "user", "action", "object_type", "object_id", "summary", "ip_address")
    list_filter = ("action",)
    search_fields = ("summary", "user__email", "ip_address")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
