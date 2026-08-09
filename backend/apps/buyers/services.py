"""Buyer-domain business services."""
from __future__ import annotations

from django.db import transaction

from backend.apps.accounts.models import User
from backend.apps.marketplace.services import MarketplaceService
from backend.apps.trade.services import TradeService
from backend.core.legacy.models import Address, BuyerProfile, DirectTradeProposal


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
        return BuyerProfile.objects.create(user=user, company_name=company_name.strip(), gst_number=gst_number, iec_code=iec_code.strip().upper(), apeda_org=apeda_org.strip() if apeda_org else None)

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
        if "company_name" in changes:
            company_name = str(changes["company_name"]).strip()
            if not company_name:
                raise ValueError("Company name is required.")
            changes["company_name"] = company_name
        if "gst_number" in changes:
            gst = str(changes["gst_number"]).strip().upper()
            if BuyerProfile.objects.filter(gst_number=gst).exclude(pk=profile.pk).exists():
                raise ValueError("This GST number is already registered.")
            changes["gst_number"] = gst
        if "iec_code" in changes:
            iec = str(changes["iec_code"]).strip().upper()
            if not iec:
                raise ValueError("IEC code is required.")
            changes["iec_code"] = iec
        for field, value in changes.items():
            setattr(profile, field, value)
        if changes:
            profile.save(update_fields=list(changes.keys()))
        return profile

    @classmethod
    @transaction.atomic
    def update_business_details(cls, *, user: User, company_name: str, first_name: str, last_name: str, village: str, district: str, state: str, pincode: str) -> BuyerProfile:
        cls._ensure_buyer(user)
        profile = cls.update_profile(user=user, changes={"company_name": company_name})
        user.first_name, user.last_name = first_name.strip(), last_name.strip()
        user.save(update_fields=["first_name", "last_name"])
        address = user.addresses.order_by("addr_id").first()
        values = {"village": village.strip(), "district": district.strip(), "state": state.strip(), "pincode": pincode.strip()}
        if address is None:
            Address.objects.create(user=user, latitude=0, longitude=0, **values)
        else:
            for field, value in values.items():
                setattr(address, field, value)
            address.save(update_fields=list(values))
        return profile

    @classmethod
    def browse_produce(cls, *, user: User, query: str | None = None, categories=None, organic: bool = False):
        cls._ensure_buyer(user)
        return MarketplaceService.browse(
            user=user,
            wing=MarketplaceService.PRODUCE,
            query=query,
            categories=categories,
            organic=organic,
        )

    @classmethod
    def get_produce_listing(cls, *, user: User, listing_id: int):
        cls._ensure_buyer(user)
        return MarketplaceService.get_active_listing(user=user, listing_id=listing_id)

    @classmethod
    def submit_proposal(cls, *, user: User, listing_id: int, quantity: float, offered_price, note: str = "") -> DirectTradeProposal:
        return TradeService.create_buyer_proposal(buyer=user, listing_id=listing_id, quantity=quantity, offered_price=offered_price, note=note)

    @classmethod
    def respond_to_proposal(cls, *, user: User, proposal_id: int, action: str) -> DirectTradeProposal:
        return TradeService.buyer_respond(buyer=user, proposal_id=proposal_id, action=action)

    @classmethod
    def revoke_buyer_proposal(cls, *, user: User, proposal_id: int) -> DirectTradeProposal:
        return TradeService.revoke_buyer_proposal(buyer=user, proposal_id=proposal_id)


__all__ = ["BuyerService"]
