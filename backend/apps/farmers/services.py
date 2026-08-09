"""Farmer-domain business services.

These services preserve the existing marketplace tables while moving farmer
rules out of the legacy HTTP layer. They are transaction-safe and enforce role
and ownership checks at the service boundary.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Mapping

from django.db import transaction

from backend.apps.accounts.models import User
from backend.core.legacy.models import (
    DirectTradeProposal,
    EscrowTransaction,
    FarmerProfile,
    InputOrder,
    ManualSoilReport,
    MarketplaceListing,
)


class FarmerService:
    @staticmethod
    def _ensure_farmer(user: User) -> None:
        if user.role != User.Role.FARMER:
            raise ValueError("Only users with the FARMER role can use farmer workflows.")
        if not user.is_active:
            raise ValueError("The farmer account is inactive.")

    @classmethod
    @transaction.atomic
    def create_profile(cls, *, user: User, aadhar_no: str, land_area: float, soil_type: str, irrigation: str) -> FarmerProfile:
        cls._ensure_farmer(user)
        if FarmerProfile.objects.filter(user=user).exists():
            raise ValueError("A farmer profile already exists for this user.")
        aadhar_no = str(aadhar_no).strip()
        if len(aadhar_no) != 12 or not aadhar_no.isdigit():
            raise ValueError("Aadhar number must contain exactly 12 digits.")
        return FarmerProfile.objects.create(user=user, aadhar_no=aadhar_no, land_area=land_area, soil_type=soil_type, irrigation=irrigation)

    @classmethod
    @transaction.atomic
    def update_profile(cls, *, user: User, changes: Mapping[str, Any]) -> FarmerProfile:
        cls._ensure_farmer(user)
        profile = FarmerProfile.objects.select_for_update().get(user=user)
        allowed = {"aadhar_no", "land_area", "soil_type", "irrigation"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported farmer profile fields: {', '.join(sorted(unknown))}")
        changes = dict(changes)
        if "aadhar_no" in changes:
            aadhar = str(changes["aadhar_no"]).strip()
            if len(aadhar) != 12 or not aadhar.isdigit():
                raise ValueError("Aadhar number must contain exactly 12 digits.")
            changes["aadhar_no"] = aadhar
        for field, value in changes.items():
            setattr(profile, field, value)
        if changes:
            profile.save(update_fields=list(changes.keys()))
        return profile

    @classmethod
    def get_profile(cls, *, user: User) -> FarmerProfile:
        cls._ensure_farmer(user)
        return FarmerProfile.objects.get(user=user)

    @classmethod
    @transaction.atomic
    def request_manual_soil_report(cls, *, user: User, land_area: float | None = None, previous_crop: str | None = None) -> ManualSoilReport:
        cls._ensure_farmer(user)
        report, _ = ManualSoilReport.objects.select_for_update().get_or_create(farmer=user, defaults={"land_area": land_area, "previous_crop": previous_crop})
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
    def complete_manual_soil_report(cls, *, user: User, nitrogen: float, phosphorus: float, potassium: float, ph: float) -> ManualSoilReport:
        cls._ensure_farmer(user)
        report = ManualSoilReport.objects.select_for_update().get(farmer=user)
        report.n, report.p, report.k, report.ph = nitrogen, phosphorus, potassium, ph
        report.request_status = "COMPLETED"
        report.save(update_fields=["n", "p", "k", "ph", "request_status"])
        return report

    @classmethod
    @transaction.atomic
    def create_produce_listing(cls, *, user: User, category: str, title: str, price: Decimal | float | str, unit_of_measure: str, available_stock: float, description: str, variety_or_brand: str | None = None, min_order_quantity: float = 1, harvest_date=None, is_organic: bool = False, grade: str | None = None, specifications: Mapping[str, Any] | None = None, image=None) -> MarketplaceListing:
        cls._ensure_farmer(user)
        if Decimal(str(price)) <= 0 or available_stock <= 0:
            raise ValueError("Price and stock must be greater than zero.")
        if min_order_quantity <= 0 or min_order_quantity > available_stock:
            raise ValueError("Minimum order quantity must be positive and within stock.")
        return MarketplaceListing.objects.create(listed_by=user, wing="PRODUCE", category=category, title=title.strip(), variety_or_brand=variety_or_brand.strip() if variety_or_brand else None, price=Decimal(str(price)), unit_of_measure=unit_of_measure.strip(), available_stock=available_stock, min_order_quantity=min_order_quantity, description=description.strip(), harvest_date=harvest_date, is_organic=is_organic, grade=grade, specifications=dict(specifications or {}), image=image, status="ACTIVE")

    @classmethod
    @transaction.atomic
    def update_listing(cls, *, user: User, listing_id: int, changes: Mapping[str, Any]) -> MarketplaceListing:
        cls._ensure_farmer(user)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, listed_by=user, wing="PRODUCE")
        allowed = {"category", "title", "variety_or_brand", "price", "unit_of_measure", "available_stock", "min_order_quantity", "description", "harvest_date", "is_organic", "grade", "specifications", "status"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported listing fields: {', '.join(sorted(unknown))}")
        changes = dict(changes)
        if "price" in changes and Decimal(str(changes["price"])) <= 0:
            raise ValueError("Price must be greater than zero.")
        if "available_stock" in changes and float(changes["available_stock"]) < 0:
            raise ValueError("Stock cannot be negative.")
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
        cls._ensure_farmer(user)
        MarketplaceListing.objects.get(pk=listing_id, listed_by=user, wing="PRODUCE").delete()

    @classmethod
    def list_inventory(cls, *, user: User):
        cls._ensure_farmer(user)
        return MarketplaceListing.objects.filter(listed_by=user, wing="PRODUCE").order_by("-created_at")

    @classmethod
    @transaction.atomic
    def send_trade_proposal(cls, *, user: User, listing_id: int, buyer_id: int, message: str = "", hide_listing: bool = False) -> DirectTradeProposal:
        cls._ensure_farmer(user)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, listed_by=user, wing="PRODUCE", status__in=["ACTIVE", "HIDDEN"])
        buyer = User.objects.get(pk=buyer_id, role=User.Role.BUYER, is_active=True, is_verified=True)
        if DirectTradeProposal.objects.filter(listing=listing, farmer=user, buyer=buyer, status="PENDING").exists():
            raise ValueError("A pending proposal already exists for this buyer and listing.")
        proposal = DirectTradeProposal.objects.create(listing=listing, farmer=user, buyer=buyer, message=message.strip(), status="PENDING")
        if hide_listing:
            listing.status = "HIDDEN"
            listing.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def respond_to_trade_proposal(cls, *, user: User, proposal_id: int, action: str, farmer_message: str = "") -> DirectTradeProposal:
        cls._ensure_farmer(user)
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, farmer=user)
        if proposal.status != "PENDING":
            raise ValueError("This proposal has already been processed.")
        action = action.upper()
        if action not in {"ACCEPT", "REJECT", "CANCEL"}:
            raise ValueError("Unsupported proposal action.")
        proposal.status = {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "CANCEL": "CANCELLED"}[action]
        if farmer_message:
            proposal.message = f"{proposal.message or ''}\nFarmer: {farmer_message}".strip()
            proposal.save(update_fields=["status", "message"])
        else:
            proposal.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def generate_trade_token(cls, *, user: User, proposal_id: int) -> str:
        cls._ensure_farmer(user)
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, farmer=user)
        if proposal.status != "ACCEPTED":
            raise ValueError("A trade token can only be generated for an accepted proposal.")
        token = uuid.uuid4().hex
        proposal.security_token = token
        proposal.save(update_fields=["security_token"])
        return token

    @classmethod
    @transaction.atomic
    def update_listing_from_form(cls, *, user: User, listing_id: int, changes: Mapping[str, Any]) -> MarketplaceListing:
        return cls.update_listing(user=user, listing_id=listing_id, changes=changes)

    @classmethod
    @transaction.atomic
    def place_input_order(cls, *, user: User, listing_id: int, quantity: float, payment_method: str, delivery_address: str) -> InputOrder:
        cls._ensure_farmer(user)
        product = MarketplaceListing.objects.select_for_update().get(pk=listing_id, wing="INPUT", status="ACTIVE")
        if quantity < product.min_order_quantity or quantity > product.available_stock:
            raise ValueError("Quantity must satisfy the minimum order and available stock constraints.")
        if payment_method not in {"UPI", "CARD", "COD"}:
            raise ValueError("Unsupported payment method.")
        total = Decimal(str(product.price)) * Decimal(str(quantity)) + Decimal("20.00")
        product.available_stock -= quantity
        if product.available_stock <= 0:
            product.available_stock = 0
            product.status = "OUT_OF_STOCK"
        product.save(update_fields=["available_stock", "status"])
        order = InputOrder.objects.create(farmer=user, product=product, quantity=quantity, total_amount=total, payment_method=payment_method, delivery_address=delivery_address.strip(), status="PENDING")
        EscrowTransaction.objects.create(item_purchased=product, vendor=product.listed_by, purchaser=user, amount_paid=total, payment_status="COMPLETED", security_token=f"ORDER-{order.order_id}")
        return order

    @classmethod
    def list_input_orders(cls, *, user: User, status: str | None = None, query: str | None = None):
        cls._ensure_farmer(user)
        orders = InputOrder.objects.filter(farmer=user).select_related("product", "product__listed_by").order_by("-created_at")
        if status and status != "ALL":
            orders = orders.filter(status=status)
        if query:
            orders = orders.filter(order_id__icontains=query)
        return orders

    @classmethod
    def get_input_order(cls, *, user: User, order_id: str) -> InputOrder:
        cls._ensure_farmer(user)
        return InputOrder.objects.select_related("product", "product__listed_by").get(order_id=order_id, farmer=user)


__all__ = ["FarmerService"]
