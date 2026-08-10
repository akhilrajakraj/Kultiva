#!/usr/bin/env python
"""Cross-platform Kultiva developer CLI.

Usage examples:
    python scripts/kultiva.py check
    python scripts/kultiva.py test
    python scripts/kultiva.py compile
    python scripts/kultiva.py migrate
    python scripts/kultiva.py runserver
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args: str) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    command = [PYTHON, str(ROOT / "manage.py"), *args]
    print("$", " ".join(command))
    return subprocess.call(command, cwd=ROOT, env=env)


def main() -> int:
    command = sys.argv[1:] or ["help"]

    aliases = {
        "check": ("check",),
        "migrate": ("migrate",),
        "makemigrations": ("makemigrations",),
        "runserver": ("runserver",),
        "shell": ("shell",),
        "showmigrations": ("showmigrations",),
        "test": ("test",),
    }

    if command[0] == "compile":
        result = subprocess.call(
            [PYTHON, "-m", "compileall", str(ROOT / "backend"), str(ROOT / "Kultiva")],
            cwd=ROOT,
        )
        return result

    django_command = aliases.get(command[0])
    if django_command is not None:
        return run(*django_command, *command[1:])

    if command[0] in {"help", "-h", "--help"}:
        print("Kultiva developer CLI")
        print("  check         Run Django system checks")
        print("  test          Run Django tests")
        print("  compile       Compile backend and legacy project")
        print("  migrate       Apply database migrations")
        print("  makemigrations Create migrations")
        print("  showmigrations Show migration state")
        print("  shell         Open Django shell")
        print("  runserver     Start development server")
        print("  <django cmd>  Forward any other Django management command")
        return 0

    return run(*command)


if __name__ == "__main__":
    raise SystemExit(main())
