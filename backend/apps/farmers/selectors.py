"""Read-only queries for the Farmer domain.

Selectors keep database reads out of the HTTP boundary. During migration the
legacy models remain the persistence authority; this module provides a stable
Farmer-owned read API over them.
"""
from __future__ import annotations

from django.db.models import QuerySet

from backend.apps.accounts.models import User
from backend.core.legacy.models import DirectTradeProposal, EscrowTransaction, MarketplaceListing


def get_profile(*, user: User):
    from backend.core.legacy.models import FarmerProfile
    return FarmerProfile.objects.get(user=user)


def get_primary_address(*, user: User):
    return user.addresses.first()


def list_proposals(*, user: User) -> dict[str, QuerySet]:
    base = DirectTradeProposal.objects.filter(farmer=user).select_related("listing", "buyer").order_by("-created_at")
    return {
        "pending": base.filter(status="PENDING"),
        "accepted": base.filter(status="ACCEPTED"),
        "completed": base.filter(status="COMPLETED"),
        "history": base.filter(status__in=["REJECTED", "CANCELLED"]),
    }


def get_proposal(*, user: User, proposal_id: int) -> DirectTradeProposal:
    return DirectTradeProposal.objects.select_related("listing", "buyer").get(pk=proposal_id, farmer=user)


def list_input_products() -> QuerySet:
    return MarketplaceListing.objects.filter(
        wing="INPUT", status="ACTIVE", available_stock__gt=0
    ).select_related("listed_by").order_by("-created_at")


def get_input_product(*, listing_id: int) -> MarketplaceListing:
    return MarketplaceListing.objects.get(pk=listing_id, wing="INPUT", status="ACTIVE")


def has_purchased_input(*, user: User, product: MarketplaceListing) -> bool:
    return EscrowTransaction.objects.filter(
        item_purchased=product,
        purchaser=user,
        payment_status="COMPLETED",
    ).exists()


def get_order_transaction(*, order_id: str):
    return EscrowTransaction.objects.filter(
        security_token=f"ORDER-{order_id}"
    ).first()


__all__ = [
    "get_profile",
    "get_primary_address",
    "list_proposals",
    "get_proposal",
    "list_input_products",
    "get_input_product",
    "has_purchased_input",
    "get_order_transaction",
]
