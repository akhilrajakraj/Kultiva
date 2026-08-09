"""Seller-domain HTTP views.

Views handle HTTP concerns only. SellerService owns authorization,
querying, validation, mutations and seller business rules.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from backend.apps.accounts.models import User
from backend.apps.sellers.services import SellerService


def _seller_only(request):
    return request.user.is_authenticated and request.user.role == User.Role.SELLER and request.user.is_active


def _deny(request):
    messages.error(request, "Access Denied. Vendor Portal Only.")
    return redirect("index")


def _parse_decimal(value, field_name="value"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}.") from exc


def _parse_float(value, field_name="value"):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}.") from exc


@login_required
def seller_dashboard(request):
    if not _seller_only(request):
        return _deny(request)
    metrics = SellerService.dashboard_metrics(user=request.user)
    return render(request, "seller_dashboard.html", metrics)


@login_required
def add_seller_listing(request):
    if not _seller_only(request):
        return _deny(request)
    if request.method != "POST":
        return render(request, "seller_add_item.html")
    try:
        raw_specs = request.POST.get("specifications", "{}")
        try:
            specifications = json.loads(raw_specs) if raw_specs else {}
        except json.JSONDecodeError as exc:
            raise ValueError("Specifications must contain valid JSON.") from exc
        listing = SellerService.create_listing(
            user=request.user,
            category=request.POST.get("category", "").strip(),
            title=request.POST.get("title", "").strip(),
            price=_parse_decimal(request.POST.get("price"), "price"),
            unit_of_measure=request.POST.get("unit_of_measure", "").strip(),
            available_stock=_parse_float(request.POST.get("available_stock"), "stock"),
            min_order_quantity=_parse_float(request.POST.get("min_order_quantity", 1), "minimum order quantity"),
            variety_or_brand=request.POST.get("variety_or_brand") or None,
            description=request.POST.get("description", "").strip(),
            specifications=specifications,
            image=request.FILES.get("image"),
        )
        messages.success(request, f"{listing.title} was added to your inventory.")
        return redirect("manage_stock")
    except ValueError as exc:
        messages.error(request, str(exc))
        return render(request, "seller_add_item.html", {"form_error": str(exc)})


@login_required
def manage_stock(request):
    if not _seller_only(request):
        return _deny(request)
    return render(request, "manage_stock.html", {"listings": SellerService.list_inventory(user=request.user)})


@login_required
def remove_listing(request):
    if not _seller_only(request):
        return _deny(request)
    if request.method == "POST":
        try:
            SellerService.delete_listing(user=request.user, listing_id=int(request.POST.get("listing_id")))
            messages.success(request, "Listing removed successfully.")
        except (TypeError, ValueError):
            messages.error(request, "The selected listing could not be removed.")
    return redirect("manage_stock")


@login_required
def edit_listing(request, listing_id):
    if not _seller_only(request):
        return _deny(request)
    try:
        listing = SellerService.get_listing(user=request.user, listing_id=listing_id)
    except Exception as exc:
        from django.http import Http404
        if exc.__class__.__name__ == "MarketplaceListing.DoesNotExist":
            raise Http404 from exc
        raise
    if request.method == "GET":
        return render(request, "seller_edit_listing.html", {"listing": listing})
    try:
        changes = {
            "category": request.POST.get("category", listing.category).strip(),
            "title": request.POST.get("title", listing.title).strip(),
            "variety_or_brand": request.POST.get("variety_or_brand") or None,
            "price": _parse_decimal(request.POST.get("price", listing.price), "price"),
            "unit_of_measure": request.POST.get("unit_of_measure", listing.unit_of_measure).strip(),
            "available_stock": _parse_float(request.POST.get("available_stock", listing.available_stock), "stock"),
            "min_order_quantity": _parse_float(request.POST.get("min_order_quantity", listing.min_order_quantity), "minimum order quantity"),
            "description": request.POST.get("description", listing.description).strip(),
        }
        if request.POST.get("specifications"):
            try:
                changes["specifications"] = json.loads(request.POST["specifications"])
            except json.JSONDecodeError as exc:
                raise ValueError("Specifications must contain valid JSON.") from exc
        if request.POST.get("status"):
            changes["status"] = request.POST["status"]
        updated = SellerService.update_listing(user=request.user, listing_id=listing_id, changes=changes)
        if request.FILES.get("image"):
            updated.image = request.FILES["image"]
            updated.save(update_fields=["image"])
        messages.success(request, f"{updated.title} was updated successfully.")
        return redirect("manage_stock")
    except ValueError as exc:
        messages.error(request, str(exc))
        return render(request, "seller_edit_listing.html", {"listing": listing, "form_error": str(exc)})


@login_required
def seller_profile_view(request):
    if not _seller_only(request):
        return _deny(request)
    profile = SellerService.get_profile(user=request.user)
    if request.method == "POST":
        try:
            profile = SellerService.update_profile(
                user=request.user,
                changes={
                    "shop_name": request.POST.get("shop_name", profile.shop_name),
                    "license_number": request.POST.get("license_number", profile.license_number),
                    "gst_number": request.POST.get("gst_number") or None,
                    "description": request.POST.get("description") or None,
                },
            )
            messages.success(request, "Seller profile updated successfully.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "seller_profile.html", {"profile": profile})


@login_required
def seller_orders(request):
    if not _seller_only(request):
        return _deny(request)
    orders = SellerService.list_orders(
        user=request.user,
        status=request.GET.get("status", "all"),
        query=request.GET.get("q", ""),
    )
    return render(request, "seller_orders.html", {
        "orders": orders,
        "current_status": request.GET.get("status", "all"),
        "search_query": request.GET.get("q", "").strip(),
    })


@login_required
def seller_order_detail(request, order_id):
    if not _seller_only(request):
        return _deny(request)
    try:
        order = SellerService.get_order(user=request.user, order_id=order_id)
    except Exception as exc:
        from django.http import Http404
        if exc.__class__.__name__ == "InputOrder.DoesNotExist":
            raise Http404 from exc
        raise
    return render(request, "seller_order_detail.html", {"order": order})


@login_required
def update_order_status(request, order_id):
    if not _seller_only(request):
        return _deny(request)
    if request.method == "POST":
        try:
            order = SellerService.update_order_status(
                user=request.user,
                order_id=order_id,
                status=request.POST.get("status", "").upper(),
            )
            messages.success(request, f"Order {order.order_id} is now {order.status}.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("seller_order_detail", order_id=order_id)


@login_required
def seller_reports(request):
    if not _seller_only(request):
        return _deny(request)
    time_filter = request.GET.get("time_filter", "all")
    try:
        metrics = SellerService.report_metrics(user=request.user, time_filter=time_filter)
    except ValueError as exc:
        messages.error(request, str(exc))
        time_filter = "all"
        metrics = SellerService.report_metrics(user=request.user, time_filter=time_filter)
    return render(request, "seller_reports.html", {**metrics, "time_filter": time_filter})


@login_required
def seller_receipt_detail(request, order_id):
    if not _seller_only(request):
        return _deny(request)
    try:
        receipt = SellerService.receipt_data(user=request.user, order_id=order_id)
    except Exception as exc:
        from django.http import Http404
        if exc.__class__.__name__ == "InputOrder.DoesNotExist":
            raise Http404 from exc
        raise
    return render(request, "seller_receipt_detail.html", receipt)


@login_required
def export_seller_orders_csv(request):
    if not _seller_only(request):
        return _deny(request)
    orders = SellerService.list_orders(user=request.user)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="seller-orders.csv"'
    writer = csv.writer(response)
    writer.writerow(["Order ID", "Product", "Farmer", "Quantity", "Amount", "Payment", "Status", "Created At"])
    for order in orders:
        writer.writerow([
            order.order_id,
            order.product.title if order.product else "Deleted product",
            order.farmer.username,
            order.quantity,
            order.total_amount,
            order.payment_method,
            order.status,
            order.created_at.isoformat(),
        ])
    return response


__all__ = [
    "seller_dashboard", "add_seller_listing", "manage_stock", "remove_listing",
    "edit_listing", "seller_profile_view", "seller_orders", "seller_order_detail",
    "update_order_status", "seller_reports", "seller_receipt_detail",
    "export_seller_orders_csv",
]
