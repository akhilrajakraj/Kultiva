"""Farmer HTTP boundary.

This module keeps the existing route names and templates while delegating
state-changing operations to FarmerService. The legacy models remain the
physical database authority during the extraction phase.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from backend.apps.farmers.services import FarmerService
from backend.core.legacy.models import DirectTradeProposal, EscrowTransaction, ManualSoilReport, MarketplaceListing


def _farmer(request):
    if not request.user.is_authenticated or request.user.role != request.user.Role.FARMER:
        return None
    return request.user


@login_required
def profile(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    profile_obj = FarmerService.get_profile(user=user)
    address = user.addresses.first()
    if request.method == "POST":
        changes = {field: request.POST.get(field) for field in ("aadhar_no", "land_area", "soil_type", "irrigation", "kissan_id") if field in request.POST}
        try:
            if changes:
                FarmerService.update_profile(user=user, changes=changes)
            if address:
                for field in ("village", "district", "state", "pincode", "latitude", "longitude"):
                    if field in request.POST:
                        setattr(address, field, request.POST.get(field) or None)
                address.save()
            messages.success(request, "Farmer profile updated successfully.")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect("farmer_profile")
    aadhar = profile_obj.aadhar_no or ""
    return render(request, "farmer_profile.html", {"profile": profile_obj, "address": address, "masked_aadhar": ("********" + aadhar[-4:]) if len(aadhar) >= 4 else "****"})


@login_required
def add_listing(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method == "POST":
        try:
            FarmerService.create_produce_listing(user=user, category=request.POST.get("category", ""), title=request.POST.get("title", ""), price=request.POST.get("price", "0"), unit_of_measure=request.POST.get("unit_of_measure", ""), available_stock=float(request.POST.get("available_stock", "0")), min_order_quantity=float(request.POST.get("min_order_quantity", "1")), description=request.POST.get("description", ""), variety_or_brand=request.POST.get("variety_or_brand") or None, harvest_date=request.POST.get("harvest_date") or None, is_organic=request.POST.get("is_organic") == "on", grade=request.POST.get("grade") or None, specifications={key: request.POST[key] for key in ("moisture_content", "shelf_life", "broken_ratio") if request.POST.get(key)}, image=request.FILES.get("image"))
            messages.success(request, "Your harvest has been successfully listed on the marketplace!")
            return redirect("farmer_home")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
    return render(request, "domains/farmer/add_listing.html")


@login_required
def manage_crops(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    return render(request, "domains/farmer/manage_crops.html", {"listings": FarmerService.list_inventory(user=user)})


@login_required
def edit_listing(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    listing_id = request.POST.get("listing_id") or request.GET.get("listing_id")
    if not listing_id:
        messages.error(request, "Listing ID is required.")
        return redirect("farmer_manage_crops")
    listing = get_object_or_404(MarketplaceListing, pk=listing_id, listed_by=user, wing="PRODUCE")
    if request.method == "POST":
        try:
            changes = {field: request.POST.get(field) for field in ("category", "title", "variety_or_brand", "price", "unit_of_measure", "available_stock", "min_order_quantity", "description", "harvest_date", "grade") if field in request.POST}
            if "stock" in request.POST and "available_stock" not in changes:
                changes["available_stock"] = request.POST.get("stock")
            if "price" in changes:
                changes["price"] = Decimal(changes["price"])
            for field in ("available_stock", "min_order_quantity"):
                if field in changes:
                    changes[field] = float(changes[field])
            if "is_organic" in request.POST:
                changes["is_organic"] = request.POST.get("is_organic") == "on"
            FarmerService.update_listing(user=user, listing_id=listing.id, changes=changes)
            messages.success(request, "Listing updated successfully.")
            return redirect("farmer_manage_crops")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
    return render(request, "domains/farmer/edit_listing.html", {"listing": listing})


@login_required
def delete_listing(request, listing_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    try:
        FarmerService.delete_listing(user=user, listing_id=listing_id)
        messages.success(request, "Listing deleted successfully.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("farmer_manage_crops")


@login_required
def submit_soil_report(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method == "POST":
        try:
            address_id = int(request.POST["farm_address_id"]) if request.POST.get("farm_address_id") else None
            if address_id is not None and not user.addresses.filter(pk=address_id).exists():
                raise ValueError("The selected farm address does not belong to this farmer.")
            FarmerService.request_manual_soil_report(user=user, farm_address_id=address_id, previous_crop=request.POST.get("previous_crop") or None)
            messages.success(request, "Manual soil report request submitted.")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect("farmer_home")
    return render(request, "farmer_home.html", {"manual_report": ManualSoilReport.objects.filter(farmer=user).select_related("farm_address").order_by("-request_date").first()})


@login_required
def proposals(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    base = DirectTradeProposal.objects.filter(farmer=user).select_related("listing", "buyer").order_by("-created_at")
    context = {
        "pending": base.filter(status="PENDING"),
        "accepted": base.filter(status="ACCEPTED"),
        "completed": base.filter(status="COMPLETED"),
        "history": base.filter(status__in=["REJECTED", "CANCELLED"]),
    }
    return render(request, "domains/farmer/proposals.html", context)


@login_required
def proposal_detail(request, proposal_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    proposal = get_object_or_404(DirectTradeProposal.objects.select_related("listing", "buyer"), pk=proposal_id, farmer=user)
    formatted_specs = {k.replace("_", " "): v for k, v in (proposal.listing.specifications or {}).items()}
    can_revoke = timezone.now() - proposal.created_at <= timedelta(hours=24)
    is_buyer_initiated = bool(proposal.message and "Requested Qty:" in proposal.message)
    return render(request, "farmer_proposal_detail.html", {"proposal": proposal, "listing": proposal.listing, "buyer": proposal.buyer, "formatted_specs": formatted_specs, "is_buyer_initiated": is_buyer_initiated, "can_revoke": can_revoke})


@login_required
def send_proposal(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method != "POST":
        return redirect("farmer_home")
    try:
        hide_listing = request.POST.get("hide_listing") == "on" or request.POST.get("visibility_action") == "HIDE"
        proposal = FarmerService.send_trade_proposal(user=user, listing_id=int(request.POST["listing_id"]), buyer_id=int(request.POST["buyer_id"]), message=request.POST.get("message", ""), hide_listing=hide_listing)
        messages.success(request, "Trade proposal sent successfully.")
        return redirect("farmer_proposal_detail", proposal_id=proposal.id)
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
        return redirect("farmer_home")


@login_required
def respond_proposal(request, proposal_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method == "POST":
        try:
            FarmerService.respond_to_trade_proposal(user=user, proposal_id=proposal_id, action=request.POST.get("action", ""), farmer_message=request.POST.get("farmer_message", ""))
            messages.success(request, "Proposal response recorded.")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
    return redirect("farmer_proposal_detail", proposal_id=proposal_id)


@login_required
def generate_trade_qr(request, proposal_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method == "POST":
        try:
            FarmerService.generate_trade_token(user=user, proposal_id=proposal_id)
            messages.success(request, "Secure trade token generated successfully.")
            return redirect("farmer_proposal_detail", proposal_id=proposal_id)
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
    return redirect("farmer_proposal_detail", proposal_id=proposal_id)


@login_required
def input_market(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    products = MarketplaceListing.objects.filter(wing="INPUT", status="ACTIVE", available_stock__gt=0).select_related("listed_by").order_by("-created_at")
    return render(request, "farmer_input_market.html", {"products": products})


@login_required
def input_detail(request, listing_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    product = get_object_or_404(MarketplaceListing, pk=listing_id, wing="INPUT", status="ACTIVE")
    has_purchased = EscrowTransaction.objects.filter(item_purchased=product, purchaser=user, payment_status="COMPLETED").exists()
    formatted_specs = {k.replace("_", " "): v for k, v in (product.specifications or {}).items()}
    return render(request, "farmer_input_detail.html", {"product": product, "formatted_specs": formatted_specs, "has_purchased": has_purchased})


@login_required
def checkout(request, listing_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    product = get_object_or_404(MarketplaceListing, pk=listing_id, wing="INPUT", status="ACTIVE")
    address = user.addresses.first()
    qty = float(request.POST.get("quantity", 1)) if request.method == "POST" else 1
    total = product.price * Decimal(str(qty)) + Decimal("20.00")
    return render(request, "farmer_checkout.html", {"product": product, "address": address, "quantity": qty, "total": total})


@login_required
def process_order(request, listing_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method != "POST":
        return redirect("farmer_checkout", listing_id=listing_id)
    try:
        qty = float(request.POST.get("quantity", 1))
        payment_mode = request.POST.get("payment_mode", "UPI")
        address = user.addresses.first()
        address_text = f"{address.village}, {address.district}, {address.state} - {address.pincode}" if address else "Address Pending"
        order = FarmerService.place_input_order(user=user, listing_id=listing_id, quantity=qty, payment_method=payment_mode, delivery_address=address_text)
        messages.success(request, f"Order {order.order_id} placed successfully.")
        return redirect("farmer_order_details", order_id=order.order_id)
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
        return redirect("farmer_checkout", listing_id=listing_id)


@login_required
def payment_gateway(request, listing_id: int):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    if request.method == "POST":
        return process_order(request, listing_id)
    product = get_object_or_404(MarketplaceListing, pk=listing_id, wing="INPUT", status="ACTIVE")
    qty = float(request.GET.get("quantity", 1))
    return render(request, "dummy_payment_gateway.html", {"product": product, "quantity": qty, "total": product.price * Decimal(str(qty)) + Decimal("20.00")})


@login_required
def orders(request):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    return render(request, "farmer_orders.html", {"orders": FarmerService.list_input_orders(user=user, status=request.GET.get("status"), query=request.GET.get("q")), "current_status": request.GET.get("status", "ALL"), "search_query": request.GET.get("q", "")})


@login_required
def order_detail(request, order_id: str):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    order = FarmerService.get_input_order(user=user, order_id=order_id)
    return render(request, "farmer_order_details.html", {"order": order, "product": order.product, "txn": EscrowTransaction.objects.filter(security_token=f"ORDER-{order.order_id}").first()})


@login_required
def invoice_detail(request, order_id: str):
    user = _farmer(request)
    if user is None:
        return redirect("index")
    order = FarmerService.get_input_order(user=user, order_id=order_id)
    return render(request, "farmer_invoice_detail.html", {"order": order, "product": order.product, "txn": EscrowTransaction.objects.filter(security_token=f"ORDER-{order.order_id}").first()})


__all__ = ["profile", "add_listing", "manage_crops", "edit_listing", "delete_listing", "submit_soil_report", "proposals", "proposal_detail", "send_proposal", "respond_proposal", "generate_trade_qr", "input_market", "input_detail", "checkout", "process_order", "payment_gateway", "orders", "order_detail", "invoice_detail"]