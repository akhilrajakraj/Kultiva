"""Application services for farmer-owned workflows.

The service layer is intentionally thin during the migration: the canonical
Django models still live in the legacy app, while callers depend on the
farmer domain API instead of importing legacy models directly.
"""

from __future__ import annotations

from typing import Any, Mapping

from django.db import transaction

from backend.apps.accounts.models import User
from backend.apps.farmers.models import FarmerProfile, ManualSoilReport


class FarmerService:
    """Use-case operations owned by the farmer domain."""

    @staticmethod
    def _ensure_farmer(user: User) -> None:
        if user.role != User.Role.FARMER:
            raise ValueError("Only users with the FARMER role can use farmer workflows.")

    @classmethod
    @transaction.atomic
    def create_profile(
        cls,
        *,
        user: User,
        aadhar_no: str,
        land_area: float,
        soil_type: str,
        irrigation: str,
    ) -> FarmerProfile:
        """Create the farmer profile for a farmer account."""
        cls._ensure_farmer(user)

        if FarmerProfile.objects.filter(user=user).exists():
            raise ValueError("A farmer profile already exists for this user.")

        return FarmerProfile.objects.create(
            user=user,
            aadhar_no=aadhar_no,
            land_area=land_area,
            soil_type=soil_type,
            irrigation=irrigation,
        )

    @classmethod
    @transaction.atomic
    def update_profile(
        cls,
        *,
        user: User,
        changes: Mapping[str, Any],
    ) -> FarmerProfile:
        """Update allowed farmer profile fields and return the saved profile."""
        cls._ensure_farmer(user)

        profile = FarmerProfile.objects.select_for_update().get(user=user)
        allowed_fields = {"aadhar_no", "land_area", "soil_type", "irrigation"}
        unknown_fields = set(changes) - allowed_fields
        if unknown_fields:
            raise ValueError(
                f"Unsupported farmer profile fields: {', '.join(sorted(unknown_fields))}"
            )

        for field, value in changes.items():
            setattr(profile, field, value)

        if changes:
            profile.save(update_fields=list(changes.keys()))
        return profile

    @staticmethod
    def get_profile(*, user: User) -> FarmerProfile:
        """Return the farmer profile; callers handle DoesNotExist explicitly."""
        return FarmerProfile.objects.get(user=user)

    @classmethod
    @transaction.atomic
    def request_manual_soil_report(
        cls,
        *,
        user: User,
        land_area: float | None = None,
        previous_crop: str | None = None,
    ) -> ManualSoilReport:
        """Create or refresh the farmer's one-to-one manual soil request."""
        cls._ensure_farmer(user)

        report, _ = ManualSoilReport.objects.select_for_update().get_or_create(
            farmer=user,
            defaults={
                "land_area": land_area,
                "previous_crop": previous_crop,
            },
        )

        if report.request_status == "COMPLETED":
            raise ValueError("A completed manual soil report cannot be reopened automatically.")

        changed = []
        if land_area is not None:
            report.land_area = land_area
            changed.append("land_area")
        if previous_crop is not None:
            report.previous_crop = previous_crop
            changed.append("previous_crop")

        if changed:
            report.save(update_fields=changed)

        return report

    @classmethod
    @transaction.atomic
    def complete_manual_soil_report(
        cls,
        *,
        user: User,
        nitrogen: float,
        phosphorus: float,
        potassium: float,
        ph: float,
    ) -> ManualSoilReport:
        """Store lab/admin results and mark the manual report completed."""
        cls._ensure_farmer(user)

        report = ManualSoilReport.objects.select_for_update().get(farmer=user)
        report.n = nitrogen
        report.p = phosphorus
        report.k = potassium
        report.ph = ph
        report.request_status = "COMPLETED"
        report.save(update_fields=["n", "p", "k", "ph", "request_status"])
        return report


__all__ = ["FarmerService"]
