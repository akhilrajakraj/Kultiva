"""Seller-domain business services.

Seller-specific authorization remains here while generic listing lifecycle
rules are owned by MarketplaceService.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from django.db import transaction

from backend.apps.accounts.models import User
from backend.apps.marketplace.services import MarketplaceService
from backend.core.legacy.models import InputOrder, SellerProfile


class SellerService:
    @staticmethod
    def _ensure_seller(user: User) -> None:
        if user.role != User.Role.SELLER:
            raise ValueError("Only sellers can use seller workflows.")
        if not user.is_active:
            raise ValueError("The seller account is inactive.")

    @classmethod
    @transaction.atomic
    def create_profile(
        cls, *, user: User, shop_name: str, license_number: str,
        gst_number: str | None = None, description: str | None = None,
    ) -> SellerProfile:
        cls._ensure_seller(user)
        if SellerProfile.objects.filter(user=user).exists():
            raise ValueError("A seller profile already exists for this user.")
        if SellerProfile.objects.filter(shop_name__iexact=shop_name.strip()).exists():
            raise ValueError("This shop name is already registered.")
        if SellerProfile.objects.filter(license_number=license_number.strip().upper()).exists():
            raise ValueError("This license number is already registered.")
        return SellerProfile.objects.create(
            user=user, shop_name=shop_name.strip(), license_number=license_number.strip().upper(),
            gst_number=gst_number.strip().upper() if gst_number else None,
            description=description.strip()[:500] if description else None,
        )

    @classmethod
    @transaction.atomic
    def update_profile(cls, *, user: User, changes: Mapping[str, Any]) -> SellerProfile:
        cls._ensure_seller(user)
        profile = SellerProfile.objects.select_for_update().get(user=user)
        allowed = {"shop_name", "license_number", "gst_number", "description"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported seller profile fields: {', '.join(sorted(unknown))}")
        changes = dict(changes)
        if "shop_name" in changes:
            name = str(changes["shop_name"]).strip()
            if SellerProfile.objects.filter(shop_name__iexact=name).exclude(pk=profile.pk).exists():
                raise ValueError("This shop name is already registered.")
            changes["shop_name"] = name
        if "license_number" in changes:
            license_number = str(changes["license_number"]).strip().upper()
            if SellerProfile.objects.filter(license_number=license_number).exclude(pk=profile.pk).exists():
                raise ValueError("This license number is already registered.")
            changes["license_number"] = license_number
        for field, value in changes.items():
            setattr(profile, field, value)
        if changes:
            profile.save(update_fields=list(changes.keys()))
        return profile

    @classmethod
    @transaction.atomic
    def create_listing(
        cls, *, user: User, category: str, title: str,
        price: Decimal | float | str, unit_of_measure: str,
        available_stock: float, description: str,
        variety_or_brand: str | None = None, min_order_quantity: float = 1,
        specifications: Mapping[str, Any] | None = None, image=None,
    ):
        cls._ensure_seller(user)
        if not user.is_verified:
            raise ValueError("Seller verification is required before publishing inventory.")
        return MarketplaceService.create_listing(
            user=user, wing=MarketplaceService.INPUT, category=category, title=title,
            price=price, unit_of_measure=unit_of_measure, available_stock=available_stock,
            min_order_quantity=min_order_quantity, description=description,
            variety_or_brand=variety_or_brand, specifications=dict(specifications or {}), image=image,
        )

    @classmethod
    @transaction.atomic
    def update_listing(cls, *, user: User, listing_id: int, changes: Mapping[str, Any]):
        cls._ensure_seller(user)
        listing = MarketplaceService.get_active_listing(user=user, listing_id=listing_id, wing=MarketplaceService.INPUT)
        # Ownership is checked by MarketplaceService.update_listing. Permit
        # editing an out-of-stock listing as well, so stock can be restored.
        return MarketplaceService.update_listing(user=user, listing_id=listing.pk, changes=dict(changes))

    @classmethod
    @transaction.atomic
    def delete_listing(cls, *, user: User, listing_id: int) -> None:
        cls._ensure_seller(user)
        listing = MarketplaceService.get_active_listing(user=user, listing_id=listing_id, wing=MarketplaceService.INPUT)
        MarketplaceService.delete_listing(user=user, listing_id=listing.pk)

    @classmethod
    def list_inventory(cls, *, user: User):
        cls._ensure_seller(user)
        from backend.core.legacy.models import MarketplaceListing
        return MarketplaceListing.objects.filter(listed_by=user, wing=MarketplaceService.INPUT).order_by("-created_at")

    @classmethod
    @transaction.atomic
    def update_order_status(cls, *, user: User, order_id: str, status: str) -> InputOrder:
        cls._ensure_seller(user)
        order = InputOrder.objects.select_for_update().select_related("product").get(order_id=order_id)
        if not order.product or order.product.listed_by_id != user.user_id:
            raise ValueError("This order does not belong to the seller.")
        allowed_transitions = {
            "PENDING": {"SHIPPED", "CANCELLED"},
            "SHIPPED": {"DELIVERED"},
            "DELIVERED": set(),
            "CANCELLED": set(),
        }
        if status not in allowed_transitions:
            raise ValueError("Invalid order status.")
        if status not in allowed_transitions[order.status]:
            raise ValueError(f"Cannot transition order from {order.status} to {status}.")
        order.status = status
        order.save(update_fields=["status"])
        return order


__all__ = ["SellerService"]
