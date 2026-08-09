from decimal import Decimal

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.trade.services import TradeService
from backend.core.legacy.models import DirectTradeProposal, MarketplaceListing


class TradeServiceTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(username="trade-farmer", password="password", role=User.Role.FARMER, is_active=True, is_verified=True)
        self.buyer = User.objects.create_user(username="trade-buyer", password="password", role=User.Role.BUYER, is_active=True, is_verified=True)
        self.unverified = User.objects.create_user(username="trade-unverified", password="password", role=User.Role.BUYER, is_active=True, is_verified=False)
        self.listing = MarketplaceListing.objects.create(
            listed_by=self.farmer,
            wing="PRODUCE",
            category="VEGETABLES",
            title="Tomato",
            price=Decimal("50.00"),
            unit_of_measure="kg",
            available_stock=100,
            min_order_quantity=1,
            description="Fresh tomato",
            status="ACTIVE",
        )

    def test_buyer_proposal_persists_negotiated_fields_when_present(self):
        proposal = TradeService.create_buyer_proposal(buyer=self.buyer, listing_id=self.listing.pk, quantity=10, offered_price=Decimal("42.50"), note="Grade A")
        self.assertEqual(proposal.status, TradeService.PENDING)
        self.assertIn("Requested Qty:", proposal.message)
        if hasattr(proposal, "requested_quantity"):
            self.assertEqual(proposal.requested_quantity, 10)
        if hasattr(proposal, "proposed_price"):
            self.assertEqual(proposal.proposed_price, Decimal("42.50"))

    def test_unverified_farmer_initiated_buyer_is_rejected(self):
        with self.assertRaises(ValueError):
            TradeService.create_farmer_proposal(farmer=self.farmer, listing_id=self.listing.pk, buyer_id=self.unverified.pk, message="Offer")

    def test_farmer_accepts_then_generates_security_token(self):
        proposal = TradeService.create_buyer_proposal(buyer=self.buyer, listing_id=self.listing.pk, quantity=5, offered_price=40)
        TradeService.farmer_respond(farmer=self.farmer, proposal_id=proposal.pk, action="ACCEPT")
        token = TradeService.generate_security_token(farmer=self.farmer, proposal_id=proposal.pk)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, TradeService.ACCEPTED)
        self.assertEqual(proposal.security_token, token)
        self.assertTrue(token)

    def test_buyer_can_revoke_pending_proposal_within_window(self):
        proposal = TradeService.create_buyer_proposal(buyer=self.buyer, listing_id=self.listing.pk, quantity=5, offered_price=40)
        TradeService.revoke_buyer_proposal(buyer=self.buyer, proposal_id=proposal.pk)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, TradeService.CANCELLED)

    def test_processed_proposal_cannot_be_changed_again(self):
        proposal = TradeService.create_buyer_proposal(buyer=self.buyer, listing_id=self.listing.pk, quantity=5, offered_price=40)
        TradeService.farmer_respond(farmer=self.farmer, proposal_id=proposal.pk, action="REJECT")
        with self.assertRaises(ValueError):
            TradeService.buyer_respond(buyer=self.buyer, proposal_id=proposal.pk, action="ACCEPT")
