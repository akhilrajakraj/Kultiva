from django.apps import AppConfig


class MarketplaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.marketplace"
    label = "marketplace_boundary"
    verbose_name = "Marketplace Boundary"
