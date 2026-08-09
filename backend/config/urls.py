"""URL configuration for the restructured Kultiva backend.

All existing routes remain owned by the canonical legacy URL module until
route-by-route extraction is verified.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Kultiva.urls import urlpatterns  # noqa: E402,F401
