"""Admin HTTP boundary for extracted administrative workflows.

Read-heavy legacy admin pages remain available during migration. State-changing
operations delegate to AdminService so authorization and transitions have one
business boundary while existing URLs and redirects remain stable.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import