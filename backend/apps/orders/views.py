"""Order HTTP boundary.

The view layer handles authentication, request parsing and presentation.
Order creation and state transitions remain inside OrderService so the
workflow stays transactional and reusable outside HTTP.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from backend.apps.orders.services import OrderService
from backend.core.legacy.models import EscrowTransaction, MarketplaceListing


def _farmer(request):
    return (
        request.user
        if request.user.is_authenticated
        and request.user.role == request.user.Role.FARMER
        and request.user.is_active
        else None
    )


def _quantity(value) -> float:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Quantity must be a valid number.")
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    return float(quantity)


def _render_checkout(request, product, address, quantity, error=None):
    total = None
    try:
        total = OrderService.calculate_total(product=product, quantity=quantity)
    except ValueError:
        pass
    context = {
        "product": product,
        "address": address,
        "quantity": quantity,
        "total": total,
    }
    if error:
        context["form_error"] = error
    return render(request, "farmer_checkout.html", context)


@login_required
def input_market(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    products = (
        MarketplaceListing.objects.filter(
            wing="INPUT", status="ACTIVE", available_stock__gt=0
        )
        .select_related("listed_by")
        .order_by("-created_at")
    )
    return render(request, "farmer_input_market.html", {"products": products})


@login_required
def checkout(request, listing_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    product = get_object_or_404(
        MarketplaceListing, pk=listing_id, wing="INPUT", status="ACTIVE"
    )
    address = user.addresses.first()
    try:
        quantity = _quantity(request.POST.get("quantity", 1)) if request.method == "POST" else 1.0
        if quantity < float(product.min_order_quantity):
            raise ValueError("Quantity is below the product minimum order quantity.")
        if quantity > float(product.available_stock):
            raise ValueError("Quantity exceeds available stock.")
    except ValueError as exc:
        quantity = request.POST.get("quantity", 1)
        return _render_checkout(request, product, address, quantity, str(exc))
    return _render_checkout(request, product, address, quantity)


@login_required
def process_order(request, listing_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method != "POST":
        return redirect("farmer_checkout", listing_id=listing_id)
    try:
        quantity = _quantity(request.POST.get("quantity", 1))
        address = user.addresses.first()
        if address is None:
            raise ValueError("A delivery address is required before placing an order.")
        address_text = (
            f"{address.village}, {address.district}, "
            f"{address.state} - {address.pincode}"
        )
        order = OrderService.place_input_order(
            user=user,
            listing_id=listing_id,
            quantity=quantity,
            payment_method=request.POST.get("payment_mode", "UPI"),
            delivery_address=address_text,
        )
        messages.success(request, f"Order {order.order_id} placed successfully.")
        return redirect("farmer_order_details", order_id=order.order_id)
    except (ValueError, TypeError, MarketplaceListing.DoesNotExist) as exc:
        messages.error(request, str(exc))
        return redirect("farmer_checkout", listing_id=listing_id)


@login_required
def orders(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    try:
        queryset = OrderService.list_for_farmer(
            user=user,
            status=request.GET.get("status"),
            query=request.GET.get("q"),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        queryset = InputOrder.objects.none()
    return render(
        request,
        "farmer_orders.html",
        {
            "orders": queryset,
            "current_status": request.GET.get("status", "ALL"),
            "search_query": request.GET.get("q", ""),
        },
    )


@login_required
def order_detail(request, order_id: str):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    try:
        order = OrderService.get_for_farmer(user=user, order_id=order_id)
    except InputOrder.DoesNotExist:
        return redirect("farmer_orders")
    txn = EscrowTransaction.objects.filter(security_token=f"ORDER-{order.order_id}").first()
    return render(
        request,
        "farmer_order_details.html",
        {"order": order, "product": order.product, "txn": txn},
    )


@login_required
def invoice_detail(request, order_id: str):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    try:
        order = OrderService.get_for_farmer(user=user, order_id=order_id)
    except InputOrder.DoesNotExist:
        return redirect("farmer_orders")
    txn = EscrowTransaction.objects.filter(security_token=f"ORDER-{order.order_id}").first()
    return render(
        request,
        "farmer_invoice_detail.html",
        {"order": order, "product": order.product, "txn": txn},
    )


# Imported only for the empty-queryset fallback above; keeping the dependency
# local to the order boundary avoids exposing the model through callers.
from backend.core.legacy.models import InputOrder


__all__ = ["input_market", "checkout", "process_order", "orders", "order_detail", "invoice_detail"]
