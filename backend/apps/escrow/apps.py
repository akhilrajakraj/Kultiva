from django.apps import AppConfig


class EscrowConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.escrow"
    label = "escrow_boundary"
    verbose_name = "Escrow Boundary"
