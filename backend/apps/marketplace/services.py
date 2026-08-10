"""Marketplace-domain business services."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
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
    VALID_WINGS = {PRODUCE, INPUT}
    VALID_STATUSES = {ACTIVE, OUT_OF_STOCK, HIDDEN}

    @staticmethod
    def _ensure_active_user(user: User) -> None:
        if not user.is_authenticated or not user.is_active:
            raise ValueError("An active authenticated user is required.")

    @staticmethod
    def _positive_decimal(value: Any, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"Invalid {field}.")
        if result <= 0:
            raise ValueError(f"{field.title()} must be greater than zero.")
        return result

    @staticmethod
    def _positive_float(value: Any, field: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid {field}.")
        if result <= 0:
            raise ValueError(f"{field.title()} must be greater than zero.")
        return result

    @staticmethod
    def _non_negative_float(value: Any, field: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid {field}.")
        if result < 0:
            raise ValueError(f"{field.title()} cannot be negative.")
        return result

    @classmethod
    def browse(cls, *, user: User, wing: str = PRODUCE, query: str | None = None,
               categories=None, organic: bool = False, seller_id: int | None = None):
        cls._ensure_active_user(user)
        wing = str(wing).strip().upper()
        if wing not in cls.VALID_WINGS:
            raise ValueError("Unsupported marketplace wing.")
        listings = MarketplaceListing.objects.filter(wing=wing, status=cls.ACTIVE, available_stock__gt=0).select_related("listed_by")
        if query and str(query).strip():
            query = str(query).strip()
            listings = listings.filter(Q(title__icontains=query) | Q(variety_or_brand__icontains=query) | Q(description__icontains=query))
        if categories:
            categories = [str(value).strip().upper() for value in categories if str(value).strip()]
            if categories:
                listings = listings.filter(category__in=categories)
        if organic:
            listings = listings.filter(is_organic=True)
        if seller_id is not None:
            listings = listings.filter(listed_by_id=seller_id)
        return listings.order_by("-created_at")

    @classmethod
    def get_active_listing(cls, *, user: User, listing_id: int, wing: str | None = None) -> MarketplaceListing:
        cls._ensure_active_user(user)
        filters = {"pk": listing_id, "status": cls.ACTIVE, "available_stock__gt": 0}
        if wing:
            filters["wing"] = str(wing).strip().upper()
        return MarketplaceListing.objects.select_related("listed_by").get(**filters)

    @classmethod
    @transaction.atomic
    def create_listing(cls, *, user: User, wing: str, category: str, title: str, price: Decimal | float | str,
                       unit_of_measure: str, available_stock: float, description: str,
                       variety_or_brand: str | None = None, min_order_quantity: float = 1,
                       harvest_date=None, is_organic: bool = False, grade: str | None = None,
                       specifications: Mapping[str, Any] | None = None, image=None) -> MarketplaceListing:
        cls._ensure_active_user(user)
        wing = str(wing).strip().upper()
        if wing not in cls.VALID_WINGS:
            raise ValueError("Unsupported marketplace wing.")
        category = str(category or "").strip().upper()
        title = str(title or "").strip()
        unit = str(unit_of_measure or "").strip()
        description = str(description or "").strip()
        if not category or not title or not unit or not description:
            raise ValueError("Category, title, unit of measure, and description are required.")
        normalized_price = cls._positive_decimal(price, "price")
        stock = cls._positive_float(available_stock, "available stock")
        minimum = cls._positive_float(min_order_quantity, "minimum order quantity")
        if minimum > stock:
            raise ValueError("Minimum order quantity cannot exceed available stock.")
        return MarketplaceListing.objects.create(listed_by=user, wing=wing, category=category, title=title,
            variety_or_brand=variety_or_brand.strip() if variety_or_brand else None, description=description,
            price=normalized_price, unit_of_measure=unit, available_stock=stock, min_order_quantity=minimum,
            harvest_date=harvest_date, is_organic=is_organic, grade=grade.strip() if grade else None,
            specifications=dict(specifications or {}), image=image, status=cls.ACTIVE)

    @classmethod
    @transaction.atomic
    def update_listing(cls, *, user: User, listing_id: int, changes: Mapping[str, Any]) -> MarketplaceListing:
        cls._ensure_active_user(user)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, listed_by=user)
        allowed = {"category", "title", "variety_or_brand", "description", "price", "unit_of_measure", "available_stock", "min_order_quantity", "harvest_date", "is_organic", "grade", "specifications", "status", "image"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported listing fields: {', '.join(sorted(unknown))}")
        changes = dict(changes)
        if "category" in changes: changes["category"] = str(changes["category"]).strip().upper()
        if "title" in changes: changes["title"] = str(changes["title"]).strip()
        if "price" in changes: changes["price"] = cls._positive_decimal(changes["price"], "price")
        if "available_stock" in changes: changes["available_stock"] = cls._non_negative_float(changes["available_stock"], "available stock")
        if "min_order_quantity" in changes: changes["min_order_quantity"] = cls._positive_float(changes["min_order_quantity"], "minimum order quantity")
        if "status" in changes:
            status = str(changes["status"]).strip().upper()
            if status not in cls.VALID_STATUSES: raise ValueError("Unsupported listing status.")
            changes["status"] = status
        projected_stock = float(changes.get("available_stock", listing.available_stock))
        projected_minimum = float(changes.get("min_order_quantity", listing.min_order_quantity))
        if projected_stock > 0 and projected_minimum > projected_stock: raise ValueError("Minimum order quantity cannot exceed available stock.")
        if projected_stock == 0: changes["status"] = cls.OUT_OF_STOCK
        elif "status" not in changes and listing.status == cls.OUT_OF_STOCK: changes["status"] = cls.ACTIVE
        for field, value in changes.items(): setattr(listing, field, value)
        if changes: listing.save(update_fields=list(changes.keys()))
        return listing

    @classmethod
    @transaction.atomic
    def delete_listing(cls, *, user: User, listing_id: int) -> None:
        cls._ensure_active_user(user)
        MarketplaceListing.objects.get(pk=listing_id, listed_by=user).delete()


__all__ = ["MarketplaceService"]
