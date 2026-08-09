"""Buyer-domain HTTP views.

These views own request/response concerns only. Mutating workflows are
validated and executed through BuyerService.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.apps.buyers.services import BuyerService
from backend.core.legacy.models import BuyerProfile, DirectTradeProposal, ManualSoilReport, MarketplaceListing


def _buyer_only(request):
    return request.user.is_authenticated and request.user.role == User.Role.BUYER and request.user.is_active


def _decimal(value, field):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid {field}.")
    if result <= 0:
        raise ValueError(f"{field.title()} must be greater than zero.")
    return result


def _float(value, field):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field}.")
    if result <= 0:
        raise ValueError(f"{field.title()} must be greater than zero.")
    return result


@login_required
def buyer_dashboard(request):
    if not _buyer_only(request):
        messages.error(request, "Access Denied. Buyer Portal Only.")
        return redirect("index")
    sent_bids = DirectTradeProposal.objects.filter(buyer=request.user).select_related("listing", "farmer").order_by("-created_at")
    received_offers = DirectTradeProposal.objects.filter(buyer=request.user).exclude(status="CANCELLED").select_related("listing", "farmer").order_by("-created_at")
    return render(request, "domains/buyer/dashboard.html", {"sent_bids": sent_bids, "received_offers": received_offers})


@login_required
def buyer_marketplace(request):
    if not _buyer_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    query = request.GET.get("q", "").strip()
    categories = request.GET.getlist("category")
    organic = request.GET.get("organic") in {"true", "on", "1"}
    products = BuyerService.browse_produce(user=request.user, query=query, categories=categories, organic=organic)
    sort = request.GET.get("sort", "newest")
    if sort == "price_low":
        products = products.order_by("price", "-created_at")
    elif sort == "price_high":
        products = products.order_by("-price", "-created_at")
    page_obj = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(request, "domains/buyer/marketplace.html", {"products": page_obj, "category_choices": MarketplaceListing.CATEGORY_CHOICES, "selected_categories": categories})


@login_required
def buyer_product_detail(request, listing_id):
    if not _buyer_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    try:
        item = BuyerService.get_produce_listing(user=request.user, listing_id=listing_id)
    except MarketplaceListing.DoesNotExist:
        return redirect("buyer_marketplace")
    existing_proposal = DirectTradeProposal.objects.filter(listing=item, buyer=request.user, status="PENDING").first()
    soil_report = ManualSoilReport.objects.filter(farmer=item.listed_by, request_status="COMPLETED").order_by("-request_date").first()
    formatted_specs = {k.replace("_", " "): v for k, v in item.specifications.items()}
    return render(request, "domains/buyer/product_detail.html", {"item": item, "existing_proposal": existing_proposal, "soil_report": soil_report, "formatted_specs": formatted_specs})


@login_required
def buyer_profile(request):
    if not _buyer_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    profile = get_object_or_404(BuyerProfile, user=request.user)
    address = request.user.addresses.order_by("addr_id").first()
    if request.method == "POST":
        try:
            BuyerService.update_business_details(user=request.user, company_name=request.POST.get("company_name", ""), first_name=request.POST.get("first_name", ""), last_name=request.POST.get("last_name", ""), village=request.POST.get("village", ""), district=request.POST.get("district", ""), state=request.POST.get("state", ""), pincode=request.POST.get("pincode", ""))
            messages.success(request, "Business profile updated successfully.")
            return redirect("buyer_profile")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "domains/buyer/profile.html", {"profile": profile, "address": address})


@login_required
def buyer_negotiations(request):
    if not _buyer_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    sent_bids = DirectTradeProposal.objects.filter(buyer=request.user).select_related("listing", "farmer").order_by("-created_at")
    received_offers = DirectTradeProposal.objects.filter(buyer=request.user).select_related("listing", "farmer").order_by("-created_at")
    return render(request, "domains/buyer/negotiations.html", {"sent_bids": sent_bids, "received_offers": received_offers})


@login_required
def submit_buyer_proposal(request, listing_id):
    if not _buyer_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    if request.method != "POST":
        return redirect("buyer_product_detail", listing_id=listing_id)
    try:
        proposal = BuyerService.submit_proposal(user=request.user, listing_id=listing_id, quantity=_float(request.POST.get("proposed_qty"), "quantity"), offered_price=_decimal(request.POST.get("proposed_price"), "offered price"), note=request.POST.get("message", ""))
        messages.success(request, f"Proposal #{proposal.pk} submitted successfully.")
        return redirect("buyer_proposal_detail", proposal_id=proposal.pk)
    except (ValueError, MarketplaceListing.DoesNotExist) as exc:
        messages.error(request, str(exc))
        return redirect("buyer_product_detail", listing_id=listing_id)


@login_required
def buyer_proposal_detail(request, proposal_id):
    if not _buyer_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    proposal = get_object_or_404(DirectTradeProposal.objects.select_related("listing", "farmer", "buyer"), pk=proposal_id, buyer=request.user)
    formatted_specs = {k.replace("_", " "): v for k, v in proposal.listing.specifications.items()}
    is_buyer_initiated = bool(proposal.message and "Requested Qty:" in proposal.message)
    can_revoke = is_buyer_initiated and proposal.status == "PENDING" and timezone.now() - proposal.created_at <= timedelta(hours=24)
    return render(request, "domains/buyer/proposal_detail.html", {"proposal": proposal, "listing": proposal.listing, "farmer": proposal.farmer, "formatted_specs": formatted_specs, "is_buyer_initiated": is_buyer_initiated, "can_revoke": can_revoke})


@login_required
def respond_to_proposal(request, proposal_id):
    if not _buyer_only(request):
        messages.error(request, "Access Denied.")
        return redirect("index")
    if request.method != "POST":
        return redirect("buyer_proposal_detail", proposal_id=proposal_id)
    try:
        action = request.POST.get("action", "").upper()
        proposal = BuyerService.revoke_buyer_proposal(user=request.user, proposal_id=proposal_id) if action == "CANCEL" else BuyerService.respond_to_proposal(user=request.user, proposal_id=proposal_id, action=action)
        messages.success(request, f"Proposal #{proposal.pk} is now {proposal.status}.")
    except (ValueError, DirectTradeProposal.DoesNotExist) as exc:
        messages.error(request, str(exc))
    return redirect("buyer_proposal_detail", proposal_id=proposal_id)


__all__ = ["buyer_dashboard", "buyer_marketplace", "buyer_product_detail", "buyer_profile", "buyer_negotiations", "submit_buyer_proposal", "buyer_proposal_detail", "respond_to_proposal"]
