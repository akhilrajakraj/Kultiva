from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.orders"
    label = "orders_boundary"
    verbose_name = "Orders Boundary"
