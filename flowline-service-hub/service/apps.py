from django.apps import AppConfig


class ServiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "service"
    verbose_name = "Service operations"

    def ready(self):
        from . import audit  # noqa: F401  (connects sign-in audit signals)
