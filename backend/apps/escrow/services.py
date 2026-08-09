"""Escrow and secure-trade domain services.

The legacy EscrowTransaction and DirectTradeProposal tables remain the
physical database authority during extraction. This service owns business
rules without changing their schema or migration history.
"""
from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from django.db import transaction

from backend.apps.accounts.models import User
from backend.core.legacy.models import DirectTradeProposal, EscrowTransaction, MarketplaceListing


class EscrowService:
    """Own escrow transaction creation, status transitions, and trade tokens."""

    ESCROW_LOCKED = "ESCROW_LOCKED"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    ACCEPTED = "ACCEPTED"

    @staticmethod
    def _ensure_active(user: User) -> None:
        if not getattr(user, "is_authenticated", False) or not user.is_active:
            raise ValueError("An active authenticated user is required.")

    @staticmethod
    def _positive_amount(value) -> Decimal:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Escrow amount must be a valid number.")
        if amount <= 0:
            raise ValueError("Escrow amount must be greater than zero.")
        return amount

    @classmethod
    @transaction.atomic
    def create_payment_transaction(
        cls,
        *,
        purchaser: User,
        listing: MarketplaceListing,
        amount: Decimal | float | str,
        payment_status: str = ESCROW_LOCKED,
        security_token: str | None = None,
    ) -> EscrowTransaction:
        cls._ensure_active(purchaser)
        if listing is None or listing.listed_by_id is None:
            raise ValueError("A valid marketplace listing is required.")
        amount_decimal = cls._positive_amount(amount)
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
    @transaction.atomic
    def fund_proposal(cls, *, buyer: User, proposal_id: int) -> EscrowTransaction:
        """Lock the accepted proposal's negotiated value in escrow.

        Funding is idempotent for an already-funded proposal and refuses to
        create a second escrow row for the same accepted trade.
        """
        cls._ensure_active(buyer)
        if buyer.role != User.Role.BUYER:
            raise ValueError("Only buyers can fund a trade.")
        proposal = DirectTradeProposal.objects.select_for_update().select_related("listing", "farmer").get(
            pk=proposal_id, buyer=buyer
        )
        if proposal.status != cls.ACCEPTED:
            raise ValueError("Only accepted proposals can be funded.")
        if proposal.total_amount <= 0:
            raise ValueError("The proposal has no valid negotiated amount.")

        existing = EscrowTransaction.objects.select_for_update().filter(
            purchaser=buyer,
            vendor=proposal.farmer,
            item_purchased=proposal.listing,
            security_token=proposal.security_token,
        ).first()
        if existing:
            return existing

        token = proposal.security_token or uuid.uuid4().hex
        if proposal.security_token != token:
            proposal.security_token = token
            proposal.save(update_fields=["security_token"])

        return cls.create_payment_transaction(
            purchaser=buyer,
            listing=proposal.listing,
            amount=proposal.total_amount,
            payment_status=cls.ESCROW_LOCKED,
            security_token=token,
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
        proposal = DirectTradeProposal.objects.select_related("listing", "farmer", "buyer").get(pk=proposal_id)
        if user.pk not in {proposal.farmer_id, proposal.buyer_id}:
            raise ValueError("You do not have access to this trade proposal.")
        return proposal

    @classmethod
    @transaction.atomic
    def mark_payment_status(cls, *, user: User, transaction_id: str, status: str) -> EscrowTransaction:
        cls._ensure_active(user)
        if status not in {cls.ESCROW_LOCKED, cls.COMPLETED, cls.REFUNDED}:
            raise ValueError("Unsupported payment status.")
        escrow = EscrowTransaction.objects.select_for_update().get(transaction_id=transaction_id)
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

    @classmethod
    @transaction.atomic
    def release_funds(cls, *, user: User, transaction_id: str) -> EscrowTransaction:
        """Release locked funds after the trade has reached settlement."""
        cls._ensure_active(user)
        escrow = EscrowTransaction.objects.select_for_update().get(transaction_id=transaction_id)
        if escrow.purchaser_id != user.pk and escrow.vendor_id != user.pk:
            raise ValueError("You do not have access to this escrow transaction.")
        if escrow.payment_status != cls.ESCROW_LOCKED:
            raise ValueError("Only locked escrow funds can be released.")
        escrow.payment_status = cls.COMPLETED
        escrow.save(update_fields=["payment_status"])
        return escrow

    @classmethod
    @transaction.atomic
    def refund_funds(cls, *, user: User, transaction_id: str) -> EscrowTransaction:
        """Refund locked funds; completed funds cannot be silently reversed."""
        cls._ensure_active(user)
        escrow = EscrowTransaction.objects.select_for_update().get(transaction_id=transaction_id)
        if escrow.purchaser_id != user.pk and escrow.vendor_id != user.pk:
            raise ValueError("You do not have access to this escrow transaction.")
        if escrow.payment_status != cls.ESCROW_LOCKED:
            raise ValueError("Only locked escrow funds can be refunded.")
        escrow.payment_status = cls.REFUNDED
        escrow.save(update_fields=["payment_status"])
        return escrow

    @classmethod
    @transaction.atomic
    def mark_proposal_paid(cls, *, buyer: User, proposal_id: int, transaction_id: str) -> DirectTradeProposal:
        """Mark the proposal paid only when its escrow transaction is completed."""
        cls._ensure_active(buyer)
        if buyer.role != User.Role.BUYER:
            raise ValueError("Only buyers can confirm proposal payment.")
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, buyer=buyer)
        escrow = EscrowTransaction.objects.select_for_update().get(transaction_id=transaction_id)
        if escrow.purchaser_id != buyer.pk or escrow.item_purchased_id != proposal.listing_id:
            raise ValueError("The escrow transaction does not belong to this proposal.")
        if escrow.payment_status != cls.COMPLETED:
            raise ValueError("Proposal cannot be marked paid before escrow is completed.")
        if proposal.total_amount != escrow.amount_paid:
            raise ValueError("Escrow amount does not match the negotiated proposal amount.")
        proposal.is_paid = True
        proposal.save(update_fields=["is_paid"])
        return proposal


__all__ = ["EscrowService"]
