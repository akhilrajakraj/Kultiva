from decimal import Decimal

from django.test import TestCase

from backend.apps.buyers.services import BuyerService
from backend.apps.farmers.services import FarmerTradeService
from backend.apps.marketplace.services import MarketplaceService
from backend.core.legacy.models import User


class TradeServiceTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(username="farmer", password="x", role=User.Role.FARMER, is_active=True)
        self.buyer = User.objects.create_user(username="buyer", password="x", role=User.Role.BUYER, is_active=True)
        self.listing = MarketplaceService.create_listing(
            user=self.farmer,
            wing=MarketplaceService.PRODUCE,
            category="VEGETABLES",
            title="Tomato",
            price=Decimal("80.00"),
            unit_of_measure="kg",
            available_stock=100,
            min_order_quantity=5,
            description="Fresh tomatoes",
        )

    def test_buyer_can_create_and_farmer_accept_proposal(self):
        proposal = BuyerService.submit_proposal(
            user=self.buyer, listing_id=self.listing.pk, quantity=10, offered_price="75", note="Ready for pickup"
        )
        self.assertEqual(proposal.status, "PENDING")
        accepted = FarmerTradeService.respond_to_proposal(
            farmer=self.farmer, proposal_id=proposal.pk, action="ACCEPT"
        )
        self.assertEqual(accepted.status, "ACCEPTED")
        self.assertTrue(accepted.security_token)

    def test_buyer_cannot_request_more_than_stock(self):
        with self.assertRaises(ValueError):
            BuyerService.submit_proposal(
                user=self.buyer, listing_id=self.listing.pk, quantity=101, offered_price="75"
            )

    def test_buyer_cannot_submit_duplicate_pending_proposal(self):
        BuyerService.submit_proposal(
            user=self.buyer, listing_id=self.listing.pk, quantity=10, offered_price="75"
        )
        with self.assertRaises(ValueError):
            BuyerService.submit_proposal(
                user=self.buyer, listing_id=self.listing.pk, quantity=12, offered_price="74"
            )
