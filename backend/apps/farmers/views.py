"""HTTP boundary for migrated farmer workflows.

The route-compatible names are kept intentionally. State-changing farmer
operations delegate to FarmerService; untouched legacy routes remain exposed
through an explicit compatibility import until parity migration is complete.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from backend.apps.farmers.services import FarmerService
from backend.core.legacy.models import ManualSoilReport


@login_required
def farmer_profile_view(request):
    if request.user.role != request.user.Role.FARMER:
        return redirect("index")
    profile = FarmerService.get_profile(user=request.user)
    address = request.user.addresses.first()
    if request.method == "POST":
        changes = {
            field: request.POST.get(field)
            for field in ("aadhar_no", "land_area", "soil_type", "irrigation")
            if field in request.POST
        }
        try:
            if changes:
                FarmerService.update_profile(user=request.user, changes=changes)
            if address:
                for field in ("village", "district", "state", "pincode", "latitude", "longitude"):
                    if field in request.POST:
                        setattr(address, field, request.POST.get(field) or None)
                address.save()
            messages.success(request, "Farmer profile updated successfully.")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect("farmer_profile")
    aadhar = profile.aadhar_no or ""
    return render(request, "farmer_profile.html", {
        "profile": profile,
        "address": address,
        "masked_aadhar": ("********" + aadhar[-4:]) if len(aadhar) >= 4 else "****",
    })


@login_required
def add_farmer_listing(request):
    if request.user.role != request.user.Role.FARMER:
        return redirect("index")
    if request.method == "POST":
        try:
            listing = FarmerService.create_produce_listing(
                user=request.user,
                category=request.POST.get("category", "").strip(),
                title=request.POST.get("title", "").strip(),
                price=request.POST.get("price", "0"),
                unit_of_measure=request.POST.get("unit_of_measure", "").strip(),
                available_stock=float(request.POST.get("available_stock", "0")),
                min_order_quantity=float(request.POST.get("min_order_quantity", "1")),
                description=request.POST.get("description", "").strip(),
                variety_or_brand=request.POST.get("variety_or_brand") or None,
                harvest_date=request.POST.get("harvest_date") or None,
                is_organic=request.POST.get("is_organic") == "on",
                grade=request.POST.get("grade") or None,
                specifications={
                    key: request.POST[key]
                    for key in ("moisture_content", "shelf_life", "broken_ratio")
                    if request.POST.get(key)
                },
                image=request.FILES.get("image"),
            )
            messages.success(request, f"{listing.title} was listed successfully.")
            return redirect("farmer_home")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
    return render(request, "farmer_add_listing.html")


@login_required
def farmer_manage_crops(request):
    if request.user.role != request.user.Role.FARMER:
        return redirect("index")
    return render(request, "farmer_manage_crops.html", {
        "listings": FarmerService.list_inventory(user=request.user),
    })


@login_required
def delete_farmer_listing(request, listing_id: int):
    if request.user.role != request.user.Role.FARMER:
        return redirect("index")
    try:
        FarmerService.delete_listing(user=request.user, listing_id=listing_id)
        messages.success(request, "Listing deleted successfully.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("farmer_manage_crops")


@login_required
def submit_manual_soil(request):
    if request.user.role != request.user.Role.FARMER:
        return redirect("index")
    if request.method == "POST":
        try:
            FarmerService.request_manual_soil_report(
                user=request.user,
                land_area=float(request.POST["land_area"]) if request.POST.get("land_area") else None,
                previous_crop=request.POST.get("previous_crop") or None,
            )
            messages.success(request, "Manual soil report request submitted.")
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect("farmer_home")
    report = ManualSoilReport.objects.filter(farmer=request.user).first()
    return render(request, "farmer_home.html", {"manual_report": report})


# Compatibility exports for the remaining farmer routes. Each one is migrated
# separately only after feature-parity tests cover its behavior.
from backend.core.legacy.views import (  # noqa: E402
    farmer_home, edit_farmer_listing, send_trade_proposal, farmer_proposals,
    farmer_proposal_detail, generate_trade_qr, farmer_respond_proposal,
    farmer_input_market, farmer_input_detail, farmer_checkout, process_input_order,
    dummy_payment_gateway, farmer_orders, farmer_invoice_detail, farmer_order_details,
    farmer_seller_list, farmer_view_seller_profile,
)
