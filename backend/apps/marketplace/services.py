"""Marketplace-domain business services.

The legacy MarketplaceListing table remains the physical database authority
while listing rules are moved behind a reusable domain service.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from django.db import transaction
from django.db.models import Q

from backend.apps.accounts.models import User
from backend.core.legacy.models import MarketplaceListing


class MarketplaceService:
    PRODUCE = "PRODUCE"
    INPUT = "INPUT"
    ACTIVE = "ACTIVE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    HIDDEN = "HIDDEN"

    @staticmethod
    def _ensure_active_user(user: User) -> None:
        if not user.is_authenticated or not user.is_active:
            raise ValueError("An active authenticated user is required.")

    @classmethod
    def browse(cls, *, user: User, wing: str = PRODUCE, query: str | None = None, categories=None, organic: bool = False):
        cls._ensure_active_user(user)
        listings = MarketplaceListing.objects.filter(
            wing=wing,
            status=cls.ACTIVE,
            available_stock__gt=0,
        ).select_related("listed_by")
        if query:
            listings = listings.filter(
                Q(title__icontains=query)
                | Q(variety_or_brand__icontains=query)
                | Q(description__icontains=query)
            )
        if categories:
            listings = listings.filter(category__in=categories)
        if organic:
            listings = listings.filter(is_organic=True)
        return listings.order_by("-created_at")

    @classmethod
    def get_active_listing(cls, *, user: User, listing_id: int, wing: str | None = None) -> MarketplaceListing:
        cls._ensure_active_user(user)
        filters = {"pk": listing_id, "status": cls.ACTIVE}
        if wing:
            filters["wing"] = wing
        return MarketplaceListing.objects.select_related("listed_by").get(**filters)

    @classmethod
    @transaction.atomic
    def create_listing(cls, *, user: User, wing: str, category: str, title: str, price: Decimal | float | str,
                       unit_of_measure: str, available_stock: float, description: str,
                       variety_or_brand: str | None = None, min_order_quantity: float = 1,
                       harvest_date=None, is_organic: bool = False, grade: str | None = None,
                       specifications: Mapping[str, Any] | None = None, image=None) -> MarketplaceListing:
        cls._ensure_active_user(user)
        if wing not in {cls.PRODUCE, cls.INPUT}:
            raise ValueError("Unsupported marketplace wing.")
        normalized_price = Decimal(str(price))
        if normalized_price <= 0:
            raise ValueError("Price must be greater than zero.")
        if available_stock <= 0:
            raise ValueError("Available stock must be greater than zero.")
        if min_order_quantity <= 0 or min_order_quantity > available_stock:
            raise ValueError("Minimum order quantity must be positive and within stock.")
        return MarketplaceListing.objects.create(
            listed_by=user,
            wing=wing,
            category=category,
            title=title.strip(),
            variety_or_brand=variety_or_brand.strip() if variety_or_brand else None,
            description=description.strip(),
            price=normalized_price,
            unit_of_measure=unit_of_measure.strip(),
            available_stock=available_stock,
            min_order_quantity=min_order_quantity,
            harvest_date=harvest_date,
            is_organic=is_organic,
            grade=grade.strip() if grade else None,
            specifications=dict(specifications or {}),
            image=image,
            status=cls.ACTIVE,
        )

    @classmethod
    @transaction.atomic
    def update_listing(cls, *, user: User, listing_id: int, changes: Mapping[str, Any]) -> MarketplaceListing:
        cls._ensure_active_user(user)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, listed_by=user)
        allowed = {
            "category", "title", "variety_or_brand", "description", "price", "unit_of_measure",
            "available_stock", "min_order_quantity", "harvest_date", "is_organic", "grade",
            "specifications", "status", "image",
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
            raise ValueError("Minimum order quantity must be greater than zero.")
        projected_stock = float(changes.get("available_stock", listing.available_stock))
        projected_min = float(changes.get("min_order_quantity", listing.min_order_quantity))
        if projected_min > projected_stock:
            raise ValueError("Minimum order quantity cannot exceed available stock.")
        if projected_stock == 0:
            changes["status"] = cls.OUT_OF_STOCK
        for field, value in changes.items():
            setattr(listing, field, value)
        if changes:
            listing.save(update_fields=list(changes.keys()))
        return listing

    @classmethod
    @transaction.atomic
    def delete_listing(cls, *, user: User, listing_id: int) -> None:
        cls._ensure_active_user(user)
        MarketplaceListing.objects.get(pk=listing_id, listed_by=user).delete()


__all__ = ["MarketplaceService"]
