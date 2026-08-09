from django.apps import AppConfig


class FarmersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.farmers"
    label = "farmers_boundary"
    verbose_name = "Farmers Boundary"
