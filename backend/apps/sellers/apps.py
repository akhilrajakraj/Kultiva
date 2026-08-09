from django.apps import AppConfig


class SellersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.sellers"
    label = "sellers_boundary"
    verbose_name = "Sellers Boundary"
