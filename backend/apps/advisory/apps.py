from django.apps import AppConfig


class AdvisoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.advisory"
    label = "advisory_boundary"
    verbose_name = "Advisory Boundary"
