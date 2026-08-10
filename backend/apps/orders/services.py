"""Application-layer services for farmer purchases of seller inputs."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction

from backend.apps.accounts.models import User
from backend.core.legacy.models import Address, InputOrder, MarketplaceListing


class OrderService:
    """Own input-order creation and lifecycle while legacy models remain DB authority."""

    PENDING = "PENDING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    PAYMENT_METHODS = {"UPI", "CARD", "COD"}

    @staticmethod
    def _ensure_farmer(user: User) -> None:
        if not user.is_authenticated or not user.is_active:
            raise ValueError("An active authenticated user is required.")
        if user.role != User.Role.FARMER:
            raise ValueError("Only farmers can place input orders.")

    @staticmethod
    def _positive_quantity(value) -> float:
        try:
            quantity = float(value)
        except (TypeError, ValueError):
            raise ValueError("Invalid quantity.")
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        return quantity

    @staticmethod
    def _payment_method(value: str) -> str:
        method = str(value or "").strip().upper()
        if method not in OrderService.PAYMENT_METHODS:
            raise ValueError("Unsupported payment method.")
        return method

    @classmethod
    @transaction.atomic
    def create_input_order(
        cls, *, farmer: User, listing_id: int, quantity: float,
        payment_method: str, delivery_address: str | None = None,
    ) -> InputOrder:
        cls._ensure_farmer(farmer)
        quantity = cls._positive_quantity(quantity)
        payment_method = cls._payment_method(payment_method)
        listing = MarketplaceListing.objects.select_for_update().get(
            pk=listing_id, wing="INPUT", status="ACTIVE"
        )
        if quantity < float(listing.min_order_quantity):
            raise ValueError("Quantity is below the listing minimum order quantity.")
        if quantity > float(listing.available_stock):
            raise ValueError("Insufficient stock.")

        address = (delivery_address or "").strip()
        if not address:
            saved_address = Address.objects.filter(user=farmer).order_by("addr_id").first()
            if saved_address:
                address = ", ".join(
                    part for part in (
                        saved_address.village, saved_address.district,
                        saved_address.state, saved_address.pincode,
                    ) if part
                )
        if not address:
            raise ValueError("A delivery address is required.")

        total = Decimal(str(listing.price)) * Decimal(str(quantity))
        listing.available_stock = float(listing.available_stock) - quantity
        if listing.available_stock <= 0:
            listing.available_stock = 0
            listing.status = "OUT_OF_STOCK"
            listing.save(update_fields=["available_stock", "status"])
        else:
            listing.save(update_fields=["available_stock"])

        return InputOrder.objects.create(
            farmer=farmer,
            product=listing,
            quantity=quantity,
            total_amount=total,
            payment_method=payment_method,
            status=cls.PENDING,
            delivery_address=address,
        )

    @classmethod
    @transaction.atomic
    def cancel_order(cls, *, farmer: User, order_id: str) -> InputOrder:
        cls._ensure_farmer(farmer)
        order = InputOrder.objects.select_for_update().select_related("product").get(
            order_id=order_id, farmer=farmer
        )
        if order.status != cls.PENDING:
            raise ValueError("Only pending orders can be cancelled.")
        if order.product_id:
            listing = MarketplaceListing.objects.select_for_update().get(pk=order.product_id)
            listing.available_stock = float(listing.available_stock) + float(order.quantity)
            if listing.status == "OUT_OF_STOCK":
                listing.status = "ACTIVE"
            listing.save(update_fields=["available_stock", "status"])
        order.status = cls.CANCELLED
        order.save(update_fields=["status"])
        return order

    @classmethod
    @transaction.atomic
    def update_seller_order_status(cls, *, seller: User, order_id: str, status: str) -> InputOrder:
        if not seller.is_authenticated or not seller.is_active or seller.role != User.Role.SELLER:
            raise ValueError("Only active sellers can update input orders.")
        order = InputOrder.objects.select_for_update().select_related("product").get(order_id=order_id)
        if not order.product_id or order.product.listed_by_id != seller.user_id:
            raise ValueError("This order does not belong to the seller.")
        status = str(status or "").strip().upper()
        allowed = {
            cls.PENDING: {cls.SHIPPED, cls.CANCELLED},
            cls.SHIPPED: {cls.DELIVERED},
            cls.DELIVERED: set(),
            cls.CANCELLED: set(),
        }
        if status not in allowed:
            raise ValueError("Invalid order status.")
        if status not in allowed[order.status]:
            raise ValueError(f"Cannot transition order from {order.status} to {status}.")
        order.status = status
        order.save(update_fields=["status"])
        return order

    @classmethod
    def get_farmer_orders(cls, *, farmer: User):
        cls._ensure_farmer(farmer)
        return InputOrder.objects.filter(farmer=farmer).select_related("product").order_by("-created_at")


__all__ = ["OrderService"]
