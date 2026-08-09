from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.analytics"
    label = "analytics_boundary"
    verbose_name = "Analytics Boundary"
