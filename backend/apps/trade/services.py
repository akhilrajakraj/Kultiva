"""Business services for buyer/farmer direct agricultural trade."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import secrets

from django.db import transaction

from backend.core.legacy.models import DirectTradeProposal, MarketplaceListing, User


class TradeService:
    """Own direct-trade lifecycle rules while legacy models remain DB authority."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

    @staticmethod
    def _ensure_user(user: User, role: str) -> None:
        if not user.is_authenticated or not user.is_active:
            raise ValueError("An active authenticated user is required.")
        if user.role != role:
            raise ValueError(f"Only {role.lower()} users can use this workflow.")

    @staticmethod
    def _positive_float(value, field: str) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid {field}.")
        if value <= 0:
            raise ValueError(f"{field.title()} must be greater than zero.")
        return value

    @staticmethod
    def _positive_decimal(value, field: str) -> Decimal:
        try:
            value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"Invalid {field}.")
        if value <= 0:
            raise ValueError(f"{field.title()} must be greater than zero.")
        return value

    @classmethod
    @transaction.atomic
    def create_buyer_proposal(
        cls, *, buyer: User, listing_id: int, quantity: float,
        offered_price, note: str = "",
    ) -> DirectTradeProposal:
        cls._ensure_user(buyer, User.Role.BUYER)
        listing = MarketplaceListing.objects.select_for_update().select_related("listed_by").get(
            pk=listing_id, wing="PRODUCE", status="ACTIVE"
        )
        quantity = cls._positive_float(quantity, "quantity")
        offered_price = cls._positive_decimal(offered_price, "offered price")
        if quantity < float(listing.min_order_quantity):
            raise ValueError("Requested quantity is below the listing minimum order quantity.")
        if quantity > float(listing.available_stock):
            raise ValueError("Requested quantity exceeds available stock.")
        if listing.listed_by_id == buyer.user_id:
            raise ValueError("A buyer cannot submit a proposal on their own listing.")
        if listing.listed_by.role != User.Role.FARMER:
            raise ValueError("Direct produce trade must target a farmer listing.")
        if DirectTradeProposal.objects.filter(
            listing=listing, buyer=buyer, status=cls.PENDING
        ).exists():
            raise ValueError("An active proposal already exists for this listing.")
        total = offered_price * Decimal(str(quantity))
        return DirectTradeProposal.objects.create(
            listing=listing,
            farmer=listing.listed_by,
            buyer=buyer,
            requested_quantity=quantity,
            proposed_price=offered_price,
            total_amount=total,
            message=note.strip() if note else "",
            status=cls.PENDING,
        )

    @classmethod
    @transaction.atomic
    def buyer_respond(cls, *, buyer: User, proposal_id: int, action: str) -> DirectTradeProposal:
        cls._ensure_user(buyer, User.Role.BUYER)
        proposal = DirectTradeProposal.objects.select_for_update().get(
            pk=proposal_id, buyer=buyer
        )
        action = str(action).strip().upper()
        if proposal.status != cls.PENDING:
            raise ValueError("Only pending proposals can be accepted or rejected.")
        if action == "REJECT":
            proposal.status = cls.REJECTED
        elif action == "ACCEPT":
            proposal.status = cls.ACCEPTED
            proposal.security_token = secrets.token_urlsafe(32)
        else:
            raise ValueError("Action must be ACCEPT or REJECT.")
        proposal.save(update_fields=["status", "security_token"])
        return proposal

    @classmethod
    @transaction.atomic
    def revoke_buyer_proposal(cls, *, buyer: User, proposal_id: int) -> DirectTradeProposal:
        cls._ensure_user(buyer, User.Role.BUYER)
        proposal = DirectTradeProposal.objects.select_for_update().get(
            pk=proposal_id, buyer=buyer
        )
        if proposal.status != cls.PENDING:
            raise ValueError("Only pending proposals can be revoked.")
        proposal.status = cls.CANCELLED
        proposal.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def farmer_respond(cls, *, farmer: User, proposal_id: int, action: str) -> DirectTradeProposal:
        cls._ensure_user(farmer, User.Role.FARMER)
        proposal = DirectTradeProposal.objects.select_for_update().get(
            pk=proposal_id, farmer=farmer
        )
        action = str(action).strip().upper()
        if proposal.status != cls.PENDING:
            raise ValueError("Only pending proposals can be accepted or rejected.")
        if action == "ACCEPT":
            proposal.status = cls.ACCEPTED
            proposal.security_token = secrets.token_urlsafe(32)
        elif action == "REJECT":
            proposal.status = cls.REJECTED
        else:
            raise ValueError("Action must be ACCEPT or REJECT.")
        proposal.save(update_fields=["status", "security_token"])
        return proposal

    @classmethod
    @transaction.atomic
    def cancel_farmer_proposal(cls, *, farmer: User, proposal_id: int) -> DirectTradeProposal:
        cls._ensure_user(farmer, User.Role.FARMER)
        proposal = DirectTradeProposal.objects.select_for_update().get(
            pk=proposal_id, farmer=farmer
        )
        if proposal.status != cls.PENDING:
            raise ValueError("Only pending proposals can be cancelled.")
        proposal.status = cls.CANCELLED
        proposal.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def schedule_pickup(cls, *, farmer: User, proposal_id: int, pickup_date) -> DirectTradeProposal:
        cls._ensure_user(farmer, User.Role.FARMER)
        proposal = DirectTradeProposal.objects.select_for_update().get(
            pk=proposal_id, farmer=farmer
        )
        if proposal.status != cls.ACCEPTED:
            raise ValueError("Pickup can only be scheduled for an accepted proposal.")
        if pickup_date is None:
            raise ValueError("Pickup date is required.")
        proposal.scheduled_pickup_date = pickup_date
        proposal.save(update_fields=["scheduled_pickup_date"])
        return proposal

    @classmethod
    def get_buyer_proposals(cls, *, buyer: User):
        cls._ensure_user(buyer, User.Role.BUYER)
        return DirectTradeProposal.objects.filter(buyer=buyer).select_related("listing", "farmer").order_by("-created_at")

    @classmethod
    def get_farmer_proposals(cls, *, farmer: User):
        cls._ensure_user(farmer, User.Role.FARMER)
        return DirectTradeProposal.objects.filter(farmer=farmer).select_related("listing", "buyer").order_by("-created_at")


__all__ = ["TradeService"]
