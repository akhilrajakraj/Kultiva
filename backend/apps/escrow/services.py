"""Escrow and secure-trade domain services.

The legacy EscrowTransaction and DirectTradeProposal tables remain the
physical database authority during extraction. This service owns business
rules without changing their schema or migration history.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction

from backend.apps.accounts.models import User
from backend.core.legacy.models import DirectTradeProposal, EscrowTransaction, MarketplaceListing


class EscrowService:
    """Own escrow transaction creation, status transitions, and trade tokens."""

    ESCROW_LOCKED = "ESCROW_LOCKED"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    ACCEPTED = "ACCEPTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

    @staticmethod
    def _ensure_active(user: User) -> None:
        if not getattr(user, "is_authenticated", False) or not user.is_active:
            raise ValueError("An active authenticated user is required.")

    @classmethod
    @transaction.atomic
    def create_payment_transaction(
        cls,
        *,
        purchaser: User,
        listing: MarketplaceListing,
        amount: Decimal | float | str,
        payment_status: str = COMPLETED,
        security_token: str | None = None,
    ) -> EscrowTransaction:
        cls._ensure_active(purchaser)
        if listing is None or listing.listed_by_id is None:
            raise ValueError("A valid marketplace listing is required.")
        amount_decimal = Decimal(str(amount))
        if amount_decimal <= 0:
            raise ValueError("Escrow amount must be greater than zero.")
        if payment_status not in {cls.ESCROW_LOCKED, cls.COMPLETED, cls.REFUNDED}:
            raise ValueError("Unsupported payment status.")
        return EscrowTransaction.objects.create(
            item_purchased=listing,
            vendor=listing.listed_by,
            purchaser=purchaser,
            amount_paid=amount_decimal,
            payment_status=payment_status,
            security_token=security_token or uuid.uuid4().hex,
        )

    @classmethod
    def get_transaction_for_order(cls, *, purchaser: User, order_id: str) -> EscrowTransaction:
        cls._ensure_active(purchaser)
        return EscrowTransaction.objects.get(
            purchaser=purchaser,
            security_token=f"ORDER-{order_id}",
        )

    @classmethod
    @transaction.atomic
    def generate_trade_token(cls, *, farmer: User, proposal_id: int) -> str:
        cls._ensure_active(farmer)
        if farmer.role != User.Role.FARMER:
            raise ValueError("Only farmers can generate trade tokens.")
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, farmer=farmer)
        if proposal.status != cls.ACCEPTED:
            raise ValueError("A trade token can only be generated for an accepted proposal.")
        token = uuid.uuid4().hex
        proposal.security_token = token
        proposal.save(update_fields=["security_token"])
        return token

    @classmethod
    def get_trade_proposal(cls, *, user: User, proposal_id: int) -> DirectTradeProposal:
        cls._ensure_active(user)
        return DirectTradeProposal.objects.select_related("listing", "farmer", "buyer").get(pk=proposal_id)

    @classmethod
    @transaction.atomic
    def mark_payment_status(cls, *, user: User, transaction_id: int, status: str) -> EscrowTransaction:
        cls._ensure_active(user)
        if status not in {cls.ESCROW_LOCKED, cls.COMPLETED, cls.REFUNDED}:
            raise ValueError("Unsupported payment status.")
        escrow = EscrowTransaction.objects.select_for_update().get(pk=transaction_id)
        if escrow.purchaser_id != user.pk and escrow.vendor_id != user.pk:
            raise ValueError("You do not have access to this escrow transaction.")
        allowed = {
            cls.ESCROW_LOCKED: {cls.ESCROW_LOCKED, cls.COMPLETED, cls.REFUNDED},
            cls.COMPLETED: {cls.COMPLETED},
            cls.REFUNDED: {cls.REFUNDED},
        }
        if status not in allowed[escrow.payment_status]:
            raise ValueError(f"Cannot transition payment from {escrow.payment_status} to {status}.")
        if escrow.payment_status != status:
            escrow.payment_status = status
            escrow.save(update_fields=["payment_status"])
        return escrow


__all__ = ["EscrowService"]
