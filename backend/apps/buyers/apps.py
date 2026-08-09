from django.apps import AppConfig


class BuyersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.buyers"
    label = "buyers_boundary"
    verbose_name = "Buyers Boundary"
