"""Seller-domain business services.

These services preserve the existing marketplace tables while moving seller
rules out of the legacy HTTP layer. They are deliberately transaction-safe and
perform role/ownership checks at the service boundary.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from django.db import transaction

from backend.apps.accounts.models import User
from backend.core.legacy.models import InputOrder, MarketplaceListing, SellerProfile


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
        cls,
        *,
        user: User,
        shop_name: str,
        license_number: str,
        gst_number: str | None = None,
        description: str | None = None,
    ) -> SellerProfile:
        cls._ensure_seller(user)
        if SellerProfile.objects.filter(user=user).exists():
            raise ValueError("A seller profile already exists for this user.")
        if SellerProfile.objects.filter(shop_name__iexact=shop_name.strip()).exists():
            raise ValueError("This shop name is already registered.")
        if SellerProfile.objects.filter(license_number=license_number.strip().upper()).exists():
            raise ValueError("This license number is already registered.")
        return SellerProfile.objects.create(
            user=user,
            shop_name=shop_name.strip(),
            license_number=license_number.strip().upper(),
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
        if "shop_name" in changes:
            name = str(changes["shop_name"]).strip()
            if SellerProfile.objects.filter(shop_name__iexact=name).exclude(pk=profile.pk).exists():
                raise ValueError("This shop name is already registered.")
            changes = dict(changes)
            changes["shop_name"] = name
        if "license_number" in changes:
            license_number = str(changes["license_number"]).strip().upper()
            if SellerProfile.objects.filter(license_number=license_number).exclude(pk=profile.pk).exists():
                raise ValueError("This license number is already registered.")
            changes = dict(changes)
            changes["license_number"] = license_number
        for field, value in changes.items():
            setattr(profile, field, value)
        if changes:
            profile.save(update_fields=list(changes.keys()))
        return profile

    @classmethod
    @transaction.atomic
    def create_listing(
        cls,
        *,
        user: User,
        category: str,
        title: str,
        price: Decimal | float | str,
        unit_of_measure: str,
        available_stock: float,
        description: str,
        variety_or_brand: str | None = None,
        min_order_quantity: float = 1,
        specifications: Mapping[str, Any] | None = None,
        image=None,
    ) -> MarketplaceListing:
        cls._ensure_seller(user)
        if not user.is_verified:
            raise ValueError("Seller verification is required before publishing inventory.")
        price_decimal = Decimal(str(price))
        if price_decimal <= 0 or available_stock <= 0:
            raise ValueError("Price and stock must be greater than zero.")
        if min_order_quantity <= 0 or min_order_quantity > available_stock:
            raise ValueError("Minimum order quantity must be positive and not exceed stock.")
        return MarketplaceListing.objects.create(
            listed_by=user,
            wing="INPUT",
            category=category,
            title=title.strip(),
            variety_or_brand=variety_or_brand.strip() if variety_or_brand else None,
            price=price_decimal,
            unit_of_measure=unit_of_measure.strip(),
            available_stock=available_stock,
            min_order_quantity=min_order_quantity,
            description=description.strip(),
            specifications=dict(specifications or {}),
            image=image,
            status="ACTIVE",
        )

    @classmethod
    @transaction.atomic
    def update_listing(cls, *, user: User, listing_id: int, changes: Mapping[str, Any]) -> MarketplaceListing:
        cls._ensure_seller(user)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, listed_by=user, wing="INPUT")
        allowed = {
            "category", "title", "variety_or_brand", "price", "unit_of_measure",
            "available_stock", "min_order_quantity", "description", "specifications", "status",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported listing fields: {', '.join(sorted(unknown))}")
        changes = dict(changes)
        if "price" in changes and Decimal(str(changes["price"])) <= 0:
            raise ValueError("Price must be greater than zero.")
        if "available_stock" in changes and float(changes["available_stock"]) < 0:
            raise ValueError("Stock cannot be negative.")
        if "min_order_quantity" in changes and float(changes["min_order_quantity"]) <= 0:
            raise ValueError("Minimum order quantity must be positive.")
        if "available_stock" in changes and float(changes["available_stock"]) == 0:
            changes["status"] = "OUT_OF_STOCK"
        for field, value in changes.items():
            setattr(listing, field, value)
        if changes:
            listing.save(update_fields=list(changes.keys()))
        return listing

    @classmethod
    @transaction.atomic
    def delete_listing(cls, *, user: User, listing_id: int) -> None:
        cls._ensure_seller(user)
        listing = MarketplaceListing.objects.get(pk=listing_id, listed_by=user, wing="INPUT")
        listing.delete()

    @classmethod
    def list_inventory(cls, *, user: User):
        cls._ensure_seller(user)
        return MarketplaceListing.objects.filter(listed_by=user, wing="INPUT").order_by("-created_at")

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
