from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.reviews"
    label = "reviews_boundary"
    verbose_name = "Reviews Boundary"
