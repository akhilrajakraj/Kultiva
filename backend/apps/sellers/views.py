"""Seller-domain HTTP views.

The views are intentionally thin: authorization, request parsing and template
composition live here; business rules and mutations are delegated to
:class:`SellerService`.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.sellers.services import SellerService
from backend.core.legacy.models import InputOrder, MarketplaceListing, SellerProfile


def _seller_only(request):
    return request.user.is_authenticated and request.user.role == User.Role.SELLER and request.user.is_active


def _parse_decimal(value, field_name="value"):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}.")
    return result


def _parse_float(value, field_name="value"):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field_name}.")
    return result


@login_required
def seller_dashboard(request):
    if not _seller_only(request):
        messages.error(request, "Access Denied. Vendor Portal Only.")
        return redirect("index")

    products = SellerService.list_inventory(user=request.user)
    orders = InputOrder.objects.filter(product__listed_by=request.user).select_related("product", "farmer")
    valid_orders = orders.exclude(status="CANCELLED")
    total_revenue = valid_orders.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    low_stock_items = products.filter(available_stock__lt=10).order_by("available_stock")[:5]
    top_products = products.annotate(total_sold=Sum("inputorder__quantity")).filter(total_sold__isnull=False).order_by("-total_sold")[:5]

    chart_labels, chart_data = [], []
    now = timezone.now()
    for months_back in range(5, -1, -1):
        # A fixed 30-day interval preserves the legacy dashboard's six-point contract.
        target = now - timezone.timedelta(days=30 * months_back)
        chart_labels.append(target.strftime("%b"))
        revenue = valid_orders.filter(
            created_at__year=target.year, created_at__month=target.month
        ).aggregate(total=Sum("total_amount"))["total"] or 0
        chart_data.append(float(revenue))

    return render(request, "seller_dashboard.html", {
        "total_revenue": total_revenue,
        "orders_count": valid_orders.count(),
        "low_stock_items": low_stock_items,
        "top_products": top_products,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
    })


@login_required
def add_seller_listing(request):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    if request.method != "POST":
        return render(request, "seller_add_item.html")

    try:
        specifications = request.POST.get("specifications", "{}")
        try:
            specifications = json.loads(specifications) if specifications else {}
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
        messages.error(request, "Access Denied.")
        return redirect("index")
    return render(request, "manage_stock.html", {"listings": SellerService.list_inventory(user=request.user)})


@login_required
def remove_listing(request):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    if request.method == "POST":
        try:
            listing_id = int(request.POST.get("listing_id"))
            SellerService.delete_listing(user=request.user, listing_id=listing_id)
            messages.success(request, "Listing removed successfully.")
        except (TypeError, ValueError, MarketplaceListing.DoesNotExist):
            messages.error(request, "The selected listing could not be removed.")
    return redirect("manage_stock")


@login_required
def edit_listing(request, listing_id):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    listing = get_object_or_404(MarketplaceListing, pk=listing_id, listed_by=request.user, wing="INPUT")
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
    except (ValueError, MarketplaceListing.DoesNotExist) as exc:
        messages.error(request, str(exc))
        return render(request, "seller_edit_listing.html", {"listing": listing, "form_error": str(exc)})


@login_required
def seller_profile_view(request):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    profile = get_object_or_404(SellerProfile, user=request.user)
    if request.method == "POST":
        try:
            SellerService.update_profile(user=request.user, changes={
                "shop_name": request.POST.get("shop_name", profile.shop_name),
                "license_number": request.POST.get("license_number", profile.license_number),
                "gst_number": request.POST.get("gst_number") or None,
                "description": request.POST.get("description") or None,
            })
            messages.success(request, "Seller profile updated successfully.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "seller_profile.html", {"profile": profile})


@login_required
def seller_orders(request):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    orders = InputOrder.objects.filter(product__listed_by=request.user).select_related("product", "farmer").order_by("-created_at")
    status_filter = request.GET.get("status", "all")
    if status_filter != "all":
        orders = orders.filter(status=status_filter.upper())
    query = request.GET.get("q", "").strip()
    if query:
        from django.db.models import Q
        orders = orders.filter(Q(order_id__icontains=query) | Q(product__title__icontains=query) | Q(farmer__username__icontains=query))
    return render(request, "seller_orders.html", {
        "orders": orders,
        "current_status": status_filter,
        "search_query": query,
    })


@login_required
def seller_order_detail(request, order_id):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    order = get_object_or_404(InputOrder.objects.select_related("product", "farmer"), order_id=order_id, product__listed_by=request.user)
    return render(request, "seller_order_detail.html", {"order": order})


@login_required
def update_order_status(request, order_id):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    if request.method == "POST":
        try:
            order = SellerService.update_order_status(
                user=request.user,
                order_id=order_id,
                status=request.POST.get("status", "").upper(),
            )
            messages.success(request, f"Order {order.order_id} is now {order.status}.")
        except (ValueError, InputOrder.DoesNotExist) as exc:
            messages.error(request, str(exc))
    return redirect("seller_order_detail", order_id=order_id)


@login_required
def seller_reports(request):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    orders = InputOrder.objects.filter(product__listed_by=request.user).select_related("product", "farmer").order_by("-created_at")
    time_filter = request.GET.get("time_filter", "all")
    now = timezone.now()
    if time_filter == "week":
        orders = orders.filter(created_at__gte=now - timezone.timedelta(days=7))
    elif time_filter == "month":
        orders = orders.filter(created_at__year=now.year, created_at__month=now.month)
    elif time_filter == "year":
        orders = orders.filter(created_at__year=now.year)
    valid_orders = orders.exclude(status="CANCELLED")
    gross = valid_orders.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    net = gross / Decimal("1.15")
    return render(request, "seller_reports.html", {
        "total_sales": round(gross, 2),
        "net_earnings": round(net, 2),
        "gst_collected": round(gross - net, 2),
        "recent_transactions": orders[:50],
        "time_filter": time_filter,
    })


@login_required
def seller_receipt_detail(request, order_id):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    order = get_object_or_404(InputOrder.objects.select_related("product", "farmer"), order_id=order_id, product__listed_by=request.user)
    packaging_fee = Decimal("20.00")
    subtotal_inclusive = order.total_amount - packaging_fee
    gst_rate = 5 if order.product and order.product.category in {"SEEDS", "FERTILIZERS"} else 18
    taxable = subtotal_inclusive / Decimal(str(1 + gst_rate / 100))
    return render(request, "seller_receipt_detail.html", {
        "order": order,
        "subtotal": round(taxable, 2),
        "gst": round(subtotal_inclusive - taxable, 2),
        "gst_rate": gst_rate,
        "packaging_fee": packaging_fee,
    })


@login_required
def export_seller_orders_csv(request):
    if not _seller_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    orders = InputOrder.objects.filter(product__listed_by=request.user).select_related("product", "farmer").order_by("-created_at")
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
