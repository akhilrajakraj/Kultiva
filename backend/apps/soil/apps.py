from django.apps import AppConfig


class SoilConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.soil"
    label = "soil_boundary"
    verbose_name = "Soil Boundary"
