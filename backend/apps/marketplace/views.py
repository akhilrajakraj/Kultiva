"""Marketplace HTTP boundary.

Request/response concerns stay here; listing business rules live in
MarketplaceService.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from backend.apps.marketplace.services import MarketplaceService
from backend.core.legacy.models import MarketplaceListing


def _active_user(request):
    return request.user if request.user.is_authenticated and request.user.is_active else None


@login_required
def marketplace(request):
    user = _active_user(request)
    if user is None:
        return redirect("index")
    query = request.GET.get("q", "").strip()
    categories = request.GET.getlist("category")
    organic = request.GET.get("organic") in {"true", "on", "1"}
    listings = MarketplaceService.browse(user=user, query=query, categories=categories, organic=organic)
    sort = request.GET.get("sort", "newest")
    if sort == "price_low":
        listings = listings.order_by("price", "-created_at")
    elif sort == "price_high":
        listings = listings.order_by("-price", "-created_at")
    page = Paginator(listings, 12).get_page(request.GET.get("page"))
    return render(request, "buyer_marketplace.html", {
        "products": page,
        "category_choices": MarketplaceListing.CATEGORY_CHOICES,
        "selected_categories": categories,
    })


@login_required
def listing_detail(request, listing_id: int):
    user = _active_user(request)
    if user is None:
        return redirect("index")
    item = get_object_or_404(MarketplaceListing.objects.select_related("listed_by"), pk=listing_id, status="ACTIVE")
    formatted_specs = {key.replace("_", " "): value for key, value in (item.specifications or {}).items()}
    return render(request, "buyer_product_detail.html", {"item": item, "formatted_specs": formatted_specs})


@login_required
def create_listing(request):
    user = _active_user(request)
    if user is None:
        return redirect("index")
    if request.method == "POST":
        try:
            price = Decimal(str(request.POST.get("price", "0")))
            stock = float(request.POST.get("available_stock", "0"))
            minimum = float(request.POST.get("min_order_quantity", "1"))
            listing = MarketplaceService.create_listing(
                user=user,
                wing=request.POST.get("wing", "PRODUCE"),
                category=request.POST.get("category", ""),
                title=request.POST.get("title", ""),
                price=price,
                unit_of_measure=request.POST.get("unit_of_measure", ""),
                available_stock=stock,
                min_order_quantity=minimum,
                description=request.POST.get("description", ""),
                variety_or_brand=request.POST.get("variety_or_brand") or None,
                harvest_date=request.POST.get("harvest_date") or None,
                is_organic=request.POST.get("is_organic") == "on",
                grade=request.POST.get("grade") or None,
                specifications={key: request.POST[key] for key in ("moisture_content", "shelf_life", "broken_ratio") if request.POST.get(key)},
                image=request.FILES.get("image"),
            )
            messages.success(request, f"Listing #{listing.pk} created successfully.")
            return redirect("buyer_marketplace")
        except (ValueError, InvalidOperation) as exc:
            messages.error(request, str(exc))
    return render(request, "farmer_add_listing.html")


__all__ = ["marketplace", "listing_detail", "create_listing"]
