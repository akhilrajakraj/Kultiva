"""Buyer-domain business services."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from backend.apps.accounts.models import User
from backend.core.legacy.models import Address, BuyerProfile, DirectTradeProposal, MarketplaceListing


class BuyerService:
    @staticmethod
    def _ensure_buyer(user: User) -> None:
        if user.role != User.Role.BUYER:
            raise ValueError("Only buyers can use buyer workflows.")
        if not user.is_active:
            raise ValueError("The buyer account is inactive.")

    @classmethod
    @transaction.atomic
    def create_profile(cls, *, user: User, company_name: str, gst_number: str, iec_code: str, apeda_org: str | None = None) -> BuyerProfile:
        cls._ensure_buyer(user)
        gst_number = gst_number.strip().upper()
        if BuyerProfile.objects.filter(user=user).exists():
            raise ValueError("A buyer profile already exists for this user.")
        if BuyerProfile.objects.filter(gst_number=gst_number).exists():
            raise ValueError("This GST number is already registered.")
        return BuyerProfile.objects.create(
            user=user,
            company_name=company_name.strip(),
            gst_number=gst_number,
            iec_code=iec_code.strip().upper(),
            apeda_org=apeda_org.strip() if apeda_org else None,
        )

    @classmethod
    @transaction.atomic
    def update_profile(cls, *, user: User, changes: dict) -> BuyerProfile:
        cls._ensure_buyer(user)
        profile = BuyerProfile.objects.select_for_update().get(user=user)
        allowed = {"company_name", "gst_number", "iec_code", "apeda_org"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported buyer profile fields: {', '.join(sorted(unknown))}")
        changes = dict(changes)
        if "gst_number" in changes:
            gst = str(changes["gst_number"]).strip().upper()
            if BuyerProfile.objects.filter(gst_number=gst).exclude(pk=profile.pk).exists():
                raise ValueError("This GST number is already registered.")
            changes["gst_number"] = gst
        if "iec_code" in changes:
            changes["iec_code"] = str(changes["iec_code"]).strip().upper()
        for field, value in changes.items():
            setattr(profile, field, value)
        if changes:
            profile.save(update_fields=list(changes.keys()))
        return profile

    @classmethod
    @transaction.atomic
    def update_business_details(
        cls,
        *,
        user: User,
        company_name: str,
        first_name: str,
        last_name: str,
        village: str,
        district: str,
        state: str,
        pincode: str,
    ) -> BuyerProfile:
        """Update buyer operational identity and shipping hub atomically."""
        cls._ensure_buyer(user)
        profile = cls.update_profile(user=user, changes={"company_name": company_name})
        user.first_name = first_name.strip()
        user.last_name = last_name.strip()
        user.save(update_fields=["first_name", "last_name"])

        address = user.addresses.order_by("addr_id").first()
        address_values = {
            "village": village.strip(),
            "district": district.strip(),
            "state": state.strip(),
            "pincode": pincode.strip(),
        }
        if address is None:
            Address.objects.create(
                user=user,
                latitude=0,
                longitude=0,
                **address_values,
            )
        else:
            for field, value in address_values.items():
                setattr(address, field, value)
            address.save(update_fields=list(address_values.keys()))
        return profile

    @classmethod
    def browse_produce(cls, *, user: User, query: str | None = None, categories=None, organic: bool = False):
        cls._ensure_buyer(user)
        listings = MarketplaceListing.objects.filter(wing="PRODUCE", status="ACTIVE", available_stock__gt=0).select_related("listed_by")
        if query:
            from django.db.models import Q
            listings = listings.filter(Q(title__icontains=query) | Q(variety_or_brand__icontains=query) | Q(description__icontains=query))
        if categories:
            listings = listings.filter(category__in=categories)
        if organic:
            listings = listings.filter(is_organic=True)
        return listings.order_by("-created_at")

    @classmethod
    @transaction.atomic
    def submit_proposal(cls, *, user: User, listing_id: int, quantity: float, offered_price: Decimal | float | str, note: str = "") -> DirectTradeProposal:
        cls._ensure_buyer(user)
        listing = MarketplaceListing.objects.select_for_update().get(pk=listing_id, wing="PRODUCE", status="ACTIVE")
        if quantity <= 0 or quantity > listing.available_stock:
            raise ValueError("Requested quantity must be positive and within available stock.")
        price = Decimal(str(offered_price))
        if price <= 0:
            raise ValueError("Offered price must be greater than zero.")
        existing = DirectTradeProposal.objects.filter(listing=listing, buyer=user, status="PENDING").exists()
        if existing:
            raise ValueError("A pending proposal already exists for this listing.")
        message = f"Requested Qty: {quantity} {listing.unit_of_measure} | Offer Price: ₹{price}/{listing.unit_of_measure} | Note: {note.strip()}"
        return DirectTradeProposal.objects.create(
            listing=listing,
            farmer=listing.listed_by,
            buyer=user,
            message=message,
            status="PENDING",
        )

    @classmethod
    @transaction.atomic
    def respond_to_proposal(cls, *, user: User, proposal_id: int, action: str) -> DirectTradeProposal:
        cls._ensure_buyer(user)
        proposal = DirectTradeProposal.objects.select_for_update().select_related("listing", "farmer").get(pk=proposal_id, buyer=user)
        if proposal.status != "PENDING":
            raise ValueError("This proposal has already been processed.")
        action = action.upper()
        if action == "ACCEPT":
            proposal.status = "ACCEPTED"
        elif action in {"REJECT", "CANCEL"}:
            proposal.status = "REJECTED" if action == "REJECT" else "CANCELLED"
        else:
            raise ValueError("Unsupported proposal action.")
        proposal.save(update_fields=["status"])
        return proposal

    @classmethod
    @transaction.atomic
    def revoke_buyer_proposal(cls, *, user: User, proposal_id: int) -> DirectTradeProposal:
        cls._ensure_buyer(user)
        proposal = DirectTradeProposal.objects.select_for_update().get(pk=proposal_id, buyer=user)
        if proposal.status != "PENDING":
            raise ValueError("Only pending proposals can be revoked.")
        if timezone.now() - proposal.created_at > timedelta(hours=24):
            raise ValueError("The 24-hour revocation window has expired.")
        proposal.status = "CANCELLED"
        proposal.save(update_fields=["status"])
        return proposal


__all__ = ["BuyerService"]
