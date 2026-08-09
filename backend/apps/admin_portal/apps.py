from django.apps import AppConfig


class AdminPortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.admin_portal"
    label = "admin_portal_boundary"
    verbose_name = "Admin Portal Boundary"
