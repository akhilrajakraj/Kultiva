"""Farmer-domain business services.

The service layer is the compatibility-safe home for farmer use cases while
legacy models remain the physical database authority during extraction.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Mapping

import qrcode
from django.core.files.base import Content