"""Administrative use cases for the Kultiva platform.

All mutating operations enforce an admin boundary and use row locks for
state-changing financial, moderation, and verification operations.
"""
from __future__ import annotations

from django.db import transaction

from backend.apps.accounts.models import User
from backend.core.legacy.models import EscrowTransaction, InputOrder, ManualSoilReport, MarketplaceListing


class AdminService:
    @staticmethod
    def _ensure_admin(user: User) -> None:
        if user.role != User.Role.ADMIN and not user.is_superuser:
            raise PermissionError("Administrator privileges are required.")

    @classmethod
    @transaction.atomic
    def approve_user(cls, *, admin: User, user_id: int) -> User:
        cls._ensure_admin(admin)
        user = User.objects.select_for_update().get(pk=user_id)
        user.is_verified = True
        user.is_active = True
        user.save(update_fields=["is_verified", "is_active"])
        return user

    @classmethod
    @transaction.atomic
    def reject_user(cls, *, admin: User, user_id: int) -> User:
        cls._ensure_admin(admin)
        user = User.objects.select_for_update().get(pk=user_id)
        user.is_verified = False
        user.is_active = False
        user.save(update_fields=["is_verified", "is_active"])
        return user

    @classmethod
    @transaction.atomic
    def suspend_user(cls, *, admin: User, user_id: int) -> User:
        cls._ensure_admin(admin)
        user = User.objects.select_for_update().get(pk=user_id)
        if user.pk == admin.pk:
            raise ValueError("An administrator cannot suspend their own account.")
        user.is_active = False
        user.save(update_fields=["is_active"])
        return user

    @classmethod
    @transaction.atomic
    def moderate_listing(cls, *, admin: User, listing_id: int, action: str) -> MarketplaceListing:
        cls._ensure_admin(admin)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id)
        action = action.upper()
        if action == "ACTIVATE":
            if listing.available_stock <= 0:
                raise ValueError("An empty listing cannot be activated.")
            listing.status = "ACTIVE"
        elif action == "HIDE":
            listing.status = "HIDDEN"
        elif action == "BAN":
            listing.status = "BANNED"
        else:
            raise ValueError("Unsupported listing moderation action.")
        listing.save(update_fields=["status"])
        return listing

    @classmethod
    @transaction.atomic
    def update_soil_report(cls, *, admin: User, report_id: int, status: str,
                           nitrogen: float | None = None, phosphorus: float | None = None,
                           potassium: float | None = None, ph: float | None = None) -> ManualSoilReport:
        cls._ensure_admin(admin)
        if status not in {"PENDING", "COMPLETED"}:
            raise ValueError("Unsupported soil report status.")
        report = ManualSoilReport.objects.select_for_update().get(pk=report_id)
        report.request_status = status
        if status == "COMPLETED":
            if nitrogen is not None:
                report.n = nitrogen
            if phosphorus is not None:
                report.p = phosphorus
            if potassium is not None:
                report.k = potassium
            if ph is not None:
                report.ph = ph
        report.save(update_fields=["request_status", "n", "p", "k", "ph"])
        return report

    @classmethod
    @transaction.atomic
    def refund_escrow(cls, *, admin: User, transaction_id: str) -> EscrowTransaction:
        cls._ensure_admin(admin)
        transaction_obj = EscrowTransaction.objects.select_for_update().get(transaction_id=transaction_id)
        if transaction_obj.payment_status != "ESCROW_LOCKED":
            raise ValueError("Only locked escrow funds can be refunded.")
        transaction_obj.payment_status = "REFUNDED"
        transaction_obj.save(update_fields=["payment_status"])
        return transaction_obj

    @classmethod
    @transaction.atomic
    def refund_input_order(cls, *, admin: User, order_id: str) -> InputOrder:
        cls._ensure_admin(admin)
        order = InputOrder.objects.select_for_update().select_related("product").get(order_id=order_id)
        if order.status != "CANCELLED":
            raise ValueError("Only cancelled input orders are eligible for this refund workflow.")
        EscrowTransaction.objects.filter(
            purchaser=order.farmer,
            item_purchased=order.product,
            security_token=f"ORDER-{order.order_id}",
            payment_status="COMPLETED",
        ).update(payment_status="REFUNDED")
        return order

    @classmethod
    def list_pending_users(cls, *, admin: User, role: str | None = None):
        cls._ensure_admin(admin)
        users = User.objects.filter(is_active=True, is_verified=False)
        if role:
            users = users.filter(role=role)
        return users.order_by("date_joined")

    @classmethod
    def list_locked_escrow(cls, *, admin: User):
        cls._ensure_admin(admin)
        return EscrowTransaction.objects.filter(payment_status="ESCROW_LOCKED").select_related("purchaser", "vendor", "item_purchased").order_by("-created_at")


__all__ = ["AdminService"]
