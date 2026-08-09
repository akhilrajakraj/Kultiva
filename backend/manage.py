#!/usr/bin/env python
"""Kultiva Django management entrypoint for the restructured repository."""
import os
import sys
from pathlib import Path

# Allow the compatibility runtime to import the canonical legacy Django package
# when this entrypoint is invoked from either the repository root or /backend.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
