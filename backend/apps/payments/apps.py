from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.payments"
    label = "payments_boundary"
    verbose_name = "Payments Boundary"
