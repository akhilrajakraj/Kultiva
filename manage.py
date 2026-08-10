#!/usr/bin/env python
"""Repository-root Django management entrypoint for Kultiva.

This wrapper keeps the CLI stable regardless of whether commands are invoked
from the repository root or from ``backend/``. The professional runtime lives
under ``backend/``; this file is intentionally a thin compatibility entrypoint.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = REPO_ROOT / "backend"

for path in (REPO_ROOT, BACKEND_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

from django.core.management import execute_from_command_line  # noqa: E402


if __name__ == "__main__":
    execute_from_command_line(sys.argv)
