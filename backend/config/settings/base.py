"""Compatibility-first base settings for the restructured Kultiva runtime.

The legacy Django application remains the source of truth for models, migrations,
URLs, templates, static files, media and business behaviour until extraction is
fully verified. This configuration makes the new backend entrypoint execute the
same application rather than a partially reconstructed application.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_PROJECT_ROOT = REPO_ROOT / "Kultiva"

# The legacy project historically runs with its inner project directory on
# sys.path, which makes imports such as ``Kultiva.settings`` and
# ``Kultiva.models`` resolve to ``Kultiva/Kultiva``. Preserve that import
# contract for the compatibility runtime.
for path in (LEGACY_PROJECT_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from Kultiva.settings import *  # noqa: F401,F403,E402

# Keep the restructured runtime's predictable repository-relative paths.
PROJECT_ROOT = REPO_ROOT
BASE_DIR = PROJECT_ROOT

# Environment overrides are intentionally lightweight and do not change legacy
# behaviour unless explicitly supplied by the deployment environment.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", SECRET_KEY)
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", ",".join(ALLOWED_HOSTS or [])
    ).split(",")
    if h.strip()
]

TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", TIME_ZONE or "Asia/Kolkata")

# The legacy app owns these resources during the compatibility phase.
TEMPLATES[0]["DIRS"] = [PROJECT_ROOT / "Kultiva" / "templates"]
STATICFILES_DIRS = [PROJECT_ROOT / "Kultiva" / "static"]
MEDIA_ROOT = PROJECT_ROOT / "Kultiva" / "media"
MEDIA_URL = "/media/"

# Do not register placeholder domain apps: their model modules are compatibility
# exports, not independent Django models. Registering them would create duplicate
# model ownership and migrations.
