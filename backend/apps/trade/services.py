"""Direct-trade negotiation domain service."""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.core.legacy.models import DirectTradeProposal, MarketplaceListing


class TradeService:
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

    @staticmethod
    def _ensure_role(user: User, role: str) -> None:
        if not getattr(user, "is_authenticated", False) or not user.is_active:
            raise ValueError("An active authenticated user is required.")
        if user.role != role:
            raise ValueError(f"Only {role.lower()} users can use this workflow.")

    @staticmethod
    def _positive_decimal(value, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"Invalid {field}.")
        if result <= 0:
            raise ValueError(f"{field.title()} must be greater than zero.")
        return result

    @staticmethod
    def _positive_quantity(value) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            raise ValueError("Requested quantity must be a valid number.")
        if result <= 0:
            raise ValueError("Requested quantity must be greater than zero.")
        return result

    @classmethod
    @transaction.atomic
    def create_buyer_proposal(cls, *, buyer: User, listing_id: int, quantity: float, offered_price, note: str = "") -> DirectTradeProposal:
        cls._ensure_role(buyer, User.Role.BUYER)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, wing="PRODUCE", status="ACTIVE")
        quantity = cls._positive_quantity(quantity)
        if quantity > float(listing.available_stock):
            raise ValueError("Requested quantity exceeds available stock.")
        price = cls._positive_decimal(offered_price, "offered price")
        if DirectTradeProposal.objects.filter(listing=listing, buyer=buyer, status=cls.PENDING).exists():
            raise ValueError("A pending proposal already exists for this listing.")
        message = f"Requested Qty: {quantity} {listing.unit_of_measure} | Offer Price: ₹{price}/{listing.unit_of_measure} | Note: {note.strip()}"
        proposal = DirectTradeProposal.objects.create(
            listing=listing,
            farmer=listing.listed_by,
            buyer=buyer,
            message=message,
            status=cls.PENDING,
            requested_quantity=quantity,
            proposed_price=price,
            total_amount=price * Decimal(str(quantity)),
        )
        return proposal

    @classmethod
    @transaction.atomic
    def create_farmer_proposal(cls, *, farmer: User, listing_id: int, buyer_id: int, message: str = "", hide_listing: bool = False) -> DirectTradeProposal:
        cls._ensure_role(farmer, User.Role.FARMER)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, listed_by=farmer, wing="PRODUCE", status__in=["ACTIVE", "HIDDEN"])
        buyer = User.objects.get(pk=buyer_id, role=User.Role.BUYER, is_active=True, is_verified=True)
        if DirectTradeProposal.objects.filter(listing=listing, farmer=farmer, buyer=buyer, status=cls.PENDING).exists():
            raise ValueError("A pending proposal already exists for this buyer and listing.")
        proposal = DirectTradeProposal.objects.create(listing=listing, farmer=farmer, buyer=buyer, message=message.strip(), status=cls.PENDING)
        if hide_listing:
            listing.status = "HIDDEN"
            listing.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def farmer_respond(cls, *, farmer: User, proposal_id: int, action: str, farmer_message: str = "") -> DirectTradeProposal:
        cls._ensure_role(farmer, User.Role.FARMER)
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, farmer=farmer)
        if proposal.status != cls.PENDING:
            raise ValueError("This proposal has already been processed.")
        action = action.upper()
        if action not in {"ACCEPT", "REJECT", "CANCEL"}:
            raise ValueError("Unsupported proposal action.")
        proposal.status = {"ACCEPT": cls.ACCEPTED, "REJECT": cls.REJECTED, "CANCEL": cls.CANCELLED}[action]
        if farmer_message:
            proposal.message = f"{proposal.message or ''}\nFarmer: {farmer_message}".strip()
            proposal.save(update_fields=["status", "message"])
        else:
            proposal.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def buyer_respond(cls, *, buyer: User, proposal_id: int, action: str) -> DirectTradeProposal:
        cls._ensure_role(buyer, User.Role.BUYER)
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, buyer=buyer)
        if proposal.status != cls.PENDING:
            raise ValueError("This proposal has already been processed.")
        action = action.upper()
        if action not in {"ACCEPT", "REJECT", "CANCEL"}:
            raise ValueError("Unsupported proposal action.")
        proposal.status = {"ACCEPT": cls.ACCEPTED, "REJECT": cls.REJECTED, "CANCEL": cls.CANCELLED}[action]
        proposal.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def revoke_buyer_proposal(cls, *, buyer: User, proposal_id: int) -> DirectTradeProposal:
        cls._ensure_role(buyer, User.Role.BUYER)
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, buyer=buyer)
        if proposal.status != cls.PENDING:
            raise ValueError("Only pending proposals can be revoked.")
        if timezone.now() - proposal.created_at > timedelta(hours=24):
            raise ValueError("The 24-hour revocation window has expired.")
        proposal.status = cls.CANCELLED
        proposal.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def generate_security_token(cls, *, farmer: User, proposal_id: int) -> str:
        cls._ensure_role(farmer, User.Role.FARMER)
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, farmer=farmer)
        if proposal.status != cls.ACCEPTED:
            raise ValueError("A trade token can only be generated for an accepted proposal.")
        token = uuid.uuid4().hex
        proposal.security_token = token
        proposal.save(update_fields=["security_token"])
        return token

    @classmethod
    def get_buyer_proposals(cls, *, buyer: User, status: str | None = None):
        cls._ensure_role(buyer, User.Role.BUYER)
        proposals = DirectTradeProposal.objects.filter(buyer=buyer).select_related("listing", "farmer").order_by("-created_at")
        if status and status.upper() != "ALL":
            proposals = proposals.filter(status=status.upper())
        return proposals

    @classmethod
    def get_farmer_proposals(cls, *, farmer: User, status: str | None = None):
        cls._ensure_role(farmer, User.Role.FARMER)
        proposals = DirectTradeProposal.objects.filter(farmer=farmer).select_related("listing", "buyer").order_by("-created_at")
        if status and status.upper() != "ALL":
            proposals = proposals.filter(status=status.upper())
        return proposals

    @classmethod
    def complete_trade(cls, *, user: User, proposal_id: int) -> DirectTradeProposal:
        if user.role not in {User.Role.FARMER, User.Role.BUYER}:
            raise ValueError("Only trade participants can complete a trade.")
        if not user.is_active:
            raise ValueError("The account is inactive.")
        with transaction.atomic():
            proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id)
            if user.pk not in {proposal.farmer_id, proposal.buyer_id}:
                raise ValueError("You do not have access to this trade.")
            if proposal.status != cls.ACCEPTED:
                raise ValueError("Only accepted trades can be completed.")
            proposal.status = cls.COMPLETED
            proposal.save(update_fields=["status"])
            return proposal


__all__ = ["TradeService"]
