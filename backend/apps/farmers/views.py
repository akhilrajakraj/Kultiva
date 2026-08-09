"""Farmer HTTP boundary.

These exports preserve every existing farmer route while the monolithic view
implementation is decomposed into services in later migration commits.
"""
from backend.core.legacy.views import *  # noqa: F401,F403
