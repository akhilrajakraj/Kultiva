"""Order-domain business services.

InputOrder is still backed by the legacy database model during extraction.
All state-changing order operations are transactional and ownership checked.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from backend.apps.accounts.models import User
from backend.core.legacy.models import EscrowTransaction, InputOrder, MarketplaceListing


class OrderService:
    INPUT_WING = "INPUT"
    ACTIVE = "ACTIVE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PAYMENT_METHODS = {"UPI", "CARD", "COD"}

    @staticmethod
    def _ensure_farmer(user: User) -> None:
        if user.role != User.Role.FARMER or not user.is_active:
            raise ValueError("Only an active farmer can place input orders.")

    @classmethod
    def calculate_total(cls, *, product: MarketplaceListing, quantity: float, delivery_fee: Decimal | str = "20.00") -> Decimal:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        return Decimal(str(product.price)) * Decimal(str(quantity)) + Decimal(str(delivery_fee))

    @classmethod
    @transaction.atomic
    def place_input_order(cls, *, user: User, listing_id: int, quantity: float, payment_method: str, delivery_address: str) -> InputOrder:
        cls._ensure_farmer(user)
        product = MarketplaceListing.objects.select_for_update().get(
            pk=listing_id, wing=cls.INPUT_WING, status=cls.ACTIVE
        )
        quantity = float(quantity)
        if quantity < product.min_order_quantity:
            raise ValueError("Quantity is below the product minimum order quantity.")
        if quantity > product.available_stock:
            raise ValueError("Quantity exceeds available stock.")
        if payment_method not in cls.PAYMENT_METHODS:
            raise ValueError("Unsupported payment method.")
        if not delivery_address or not delivery_address.strip():
            raise ValueError("Delivery address is required.")

        total = cls.calculate_total(product=product, quantity=quantity)
        product.available_stock -= quantity
        if product.available_stock <= 0:
            product.available_stock = 0
            product.status = cls.OUT_OF_STOCK
        product.save(update_fields=["available_stock", "status"])

        order = InputOrder.objects.create(
            farmer=user,
            product=product,
            quantity=quantity,
            total_amount=total,
            payment_method=payment_method,
            status="PENDING",
            delivery_address=delivery_address.strip(),
        )
        EscrowTransaction.objects.create(
            item_purchased=product,
            vendor=product.listed_by,
            purchaser=user,
            amount_paid=total,
            payment_status="COMPLETED",
            security_token=f"ORDER-{order.order_id}",
        )
        return order

    @classmethod
    def list_for_farmer(cls, *, user: User, status: str | None = None, query: str | None = None):
        cls._ensure_farmer(user)
        orders = InputOrder.objects.filter(farmer=user).select_related("product", "product__listed_by").order_by("-created_at")
        if status and status != "ALL":
            orders = orders.filter(status=status)
        if query:
            orders = orders.filter(order_id__icontains=query)
        return orders

    @classmethod
    def get_for_farmer(cls, *, user: User, order_id: str) -> InputOrder:
        cls._ensure_farmer(user)
        return InputOrder.objects.select_related("product", "product__listed_by").get(order_id=order_id, farmer=user)

    @classmethod
    @transaction.atomic
    def update_status(cls, *, actor: User, order_id: str, status: str) -> InputOrder:
        if actor.role not in {User.Role.SELLER, User.Role.ADMIN} or not actor.is_active:
            raise ValueError("Only an active seller or admin can update order status.")
        order = InputOrder.objects.select_for_update().select_related("product").get(order_id=order_id)
        if status not in {"PENDING", "SHIPPED", "DELIVERED", "CANCELLED"}:
            raise ValueError("Unsupported order status.")
        if actor.role == User.Role.SELLER and order.product and order.product.listed_by_id != actor.pk:
            raise ValueError("You do not own this order's product.")
        if order.status == "DELIVERED" and status != "DELIVERED":
            raise ValueError("A delivered order cannot be moved backwards.")
        if order.status == "CANCELLED" and status != "CANCELLED":
            raise ValueError("A cancelled order cannot be reopened.")
        order.status = status
        order.save(update_fields=["status"])
        return order


__all__ = ["OrderService"]
