import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal

from django.test import TestCase
from django.urls import resolve, reverse

from backend.apps.accounts.models import User
from backend.apps.buyers.services import BuyerService
from backend.apps.farmers.services import FarmerService
from backend.core.legacy.models import DirectTradeProposal


class BuyerExtractionTests(TestCase):
    def _user(self, username, role):
        return User.objects.create_user(
            username=username,
            password="TestPassword!123",
            role=role,
            is_active=True,
            is_verified=True,
        )

    def setUp(self):
        self.farmer = self._user("buyer-extraction-farmer", User.Role.FARMER)
        self.buyer = self._user("buyer-extraction-buyer", User.Role.BUYER)
        FarmerService.create_profile(
            user=self.farmer,
            aadhar_no="999999999991",
            land_area=2,
            soil_type="Loamy",
            irrigation="Rain",
        )
        self.listing = FarmerService.create_produce_listing(
            user=self.farmer,
            category="GRAINS",
            title="Buyer Test Rice",
            price=Decimal("50"),
            unit_of_measure="kg",
            available_stock=100,
            description="Fresh rice",
        )

    def test_buyer_routes_resolve_to_extracted_views(self):
        from backend.apps.buyers import views

        expected = {
            "buyer_dashboard": views.buyer_dashboard,
            "buyer_marketplace": views.buyer_marketplace,
            "buyer_product_detail": views.buyer_product_detail,
            "buyer_profile": views.buyer_profile,
            "buyer_negotiations": views.buyer_negotiations,
            "submit_buyer_proposal": views.submit_buyer_proposal,
            "buyer_proposal_detail": views.buyer_proposal_detail,
            "respond_to_proposal": views.respond_to_proposal,
        }
        for name, view in expected.items():
            kwargs = {"listing_id": self.listing.pk} if name in {"buyer_product_detail", "submit_buyer_proposal"} else {}
            if name in {"buyer_proposal_detail", "respond_to_proposal"}:
                proposal = BuyerService.submit_proposal(
                    user=self.buyer,
                    listing_id=self.listing.pk,
                    quantity=2,
                    offered_price=Decimal("45"),
                )
                kwargs = {"proposal_id": proposal.pk}
            self.assertIs(resolve(reverse(name, kwargs=kwargs)).func, view)

    def test_buyer_can_browse_marketplace_and_submit_proposal(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("buyer_marketplace"), {"q": "Rice"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buyer Test Rice")

        response = self.client.post(reverse("submit_buyer_proposal", args=[self.listing.pk]), {
            "proposed_qty": "10",
            "proposed_price": "45",
            "message": "Bulk procurement",
        })
        self.assertEqual(response.status_code, 302)
        proposal = DirectTradeProposal.objects.get(buyer=self.buyer, listing=self.listing)
        self.assertEqual(proposal.status, "PENDING")
        self.assertContains(self.client.get(reverse("buyer_proposal_detail", args=[proposal.pk])), "Buyer Test Rice")

    def test_buyer_can_update_operational_profile(self):
        BuyerService.create_profile(
            user=self.buyer,
            company_name="Original Buyer",
            gst_number="22AAAAA1111A1Z5",
            iec_code="1234567890",
        )
        self.client.force_login(self.buyer)
        response = self.client.post(reverse("buyer_profile"), {
            "company_name": "Updated Buyer Pvt Ltd",
            "first_name": "Akhil",
            "last_name": "Buyer",
            "village": "Town",
            "district": "Pathanamthitta",
            "state": "Kerala",
            "pincode": "689645",
        })
        self.assertEqual(response.status_code, 302)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.first_name, "Akhil")
        self.assertEqual(self.buyer.buyer_profile.company_name, "Updated Buyer Pvt Ltd")
        self.assertEqual(self.buyer.addresses.first().district, "Pathanamthitta")

    def test_buyer_can_revoke_own_pending_proposal(self):
        proposal = BuyerService.submit_proposal(
            user=self.buyer,
            listing_id=self.listing.pk,
            quantity=5,
            offered_price=Decimal("40"),
        )
        self.client.force_login(self.buyer)
        response = self.client.post(reverse("respond_to_proposal", args=[proposal.pk]), {"action": "CANCEL"})
        self.assertEqual(response.status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "CANCELLED")
