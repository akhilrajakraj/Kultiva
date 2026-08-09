"""Base settings for the compatibility-first professional Kultiva runtime.

The legacy Django application remains the database/model migration authority in
Phase 2. The professional backend is nevertheless a real Django runtime: it
owns the entrypoint, settings, URL configuration, domain boundaries and AI
boundaries while importing the legacy implementation only at compatibility
seams.
"""
from pathlib import Path
import os
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_PROJECT_ROOT = REPO_ROOT / "Kultiva"

for path in (LEGACY_PROJECT_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from Kultiva.settings import *  # noqa: F401,F403,E402

PROJECT_ROOT = REPO_ROOT
BASE_DIR = PROJECT_ROOT

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", SECRET_KEY)
DEBUG = os.environ.get("DJANGO_DEBUG", str(DEBUG)).lower() in {"1", "true", "yes", "on"}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", ",".join(ALLOWED_HOSTS or ["localhost", "127.0.0.1"])
    ).split(",")
    if host.strip()
]

TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", TIME_ZONE or "Asia/Kolkata")
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# The legacy app owns the concrete Django models/migrations during Phase 2.
# Boundary apps are registered as migration-free shells around those models.
DOMAIN_APPS = [
    "backend.apps.accounts.apps.AccountsConfig",
    "backend.apps.admin_portal.apps.AdminPortalConfig",
    "backend.apps.advisory.apps.AdvisoryConfig",
    "backend.apps.analytics.apps.AnalyticsConfig",
    "backend.apps.buyers.apps.BuyersConfig",
    "backend.apps.escrow.apps.EscrowConfig",
    "backend.apps.farmers.apps.FarmersConfig",
    "backend.apps.marketplace.apps.MarketplaceConfig",
    "backend.apps.notifications.apps.NotificationsConfig",
    "backend.apps.orders.apps.OrdersConfig",
    "backend.apps.payments.apps.PaymentsConfig",
    "backend.apps.reviews.apps.ReviewsConfig",
    "backend.apps.sellers.apps.SellersConfig",
    "backend.apps.soil.apps.SoilConfig",
    "backend.apps.weather.apps.WeatherConfig",
]
INSTALLED_APPS = list(INSTALLED_APPS)
for app in DOMAIN_APPS:
    if app not in INSTALLED_APPS:
        INSTALLED_APPS.append(app)

TEMPLATES[0]["DIRS"] = [PROJECT_ROOT / "Kultiva" / "templates"]
STATICFILES_DIRS = [PROJECT_ROOT / "Kultiva" / "static"]
MEDIA_ROOT = PROJECT_ROOT / "Kultiva" / "media"
MEDIA_URL = "/media/"

# Keep the existing user/table/migration contract until the extraction is
# explicitly migrated with SeparateDatabaseAndState in the next phase.
AUTH_USER_MODEL = "Kultiva.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
