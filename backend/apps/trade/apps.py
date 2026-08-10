from django.apps import AppConfig


class TradeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.trade"
    label = "trade_boundary"
    verbose_name = "Direct Trade Boundary"
