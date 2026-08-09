import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal
from django.test import TestCase

from backend.ai.crop_prediction.service import predict_best_crop
from backend.apps.accounts.models import User
from backend.apps.advisory.services import get_crop_advisory
from backend.apps.admin_portal.services import AdminService
from backend.apps.buyers.services import BuyerService
from backend.apps.farmers.models import FarmerProfile, ManualSoilReport
from backend.apps.farmers.services import FarmerService
from backend.apps.sellers.services import SellerService
from backend.apps.soil.services import get_safe_defaults
from backend.apps.weather.services import get_weather
from backend.core.legacy.models import EscrowTransaction, InputOrder, MarketplaceListing


class Phase3ServiceTests(TestCase):
    def test_soil_service_returns_complete_safe_contract(self):
        data = get_safe_defaults()
        for key in ("pH", "N", "P", "K", "found", "Status"):
            self.assertIn(key, data)

    def test_advisory_service_handles_unknown_crop(self):
        self.assertIsNone(get_crop_advisory("__unknown_crop__"))

    def test_weather_service_returns_contract(self):
        data = get_weather(9.2648, 76.7870, "Pathanamthitta")
        for key in ("Temperature_C", "Humidity_Pct", "Rainfall_mm", "Source", "Status"):
            self.assertIn(key, data)

    def test_crop_prediction_service_is_callable(self):
        self.assertTrue(callable(predict_best_crop))

    def _user(self, username, role, verified=True):
        return User.objects.create_user(
            username=username,
            password="TestPassword!123",
            role=role,
            is_verified=verified,
            is_active=True,
        )

    def test_farmer_profile_and_soil_workflow(self):
        farmer = self._user("farmer", User.Role.FARMER)
        profile = FarmerService.create_profile(
            user=farmer, aadhar_no="123456789012", land_area=2.5,
            soil_type="Loamy", irrigation="Drip",
        )
        self.assertIsInstance(profile, FarmerProfile)
        report = FarmerService.request_manual_soil_report(
            user=farmer, land_area=2.5, previous_crop="Rice",
        )
        self.assertEqual(report.request_status, "PENDING")
        completed = FarmerService.complete_manual_soil_report(
            user=farmer, nitrogen=80, phosphorus=40, potassium=60, ph=6.5,
        )
        self.assertEqual(completed.request_status, "COMPLETED")
        self.assertEqual(completed.n, 80)

    def test_farmer_produce_listing_and_trade_proposal(self):
        farmer = self._user("farmer-trade", User.Role.FARMER)
        buyer = self._user("buyer-trade", User.Role.BUYER)
        FarmerService.create_profile(
            user=farmer, aadhar_no="123456789013", land_area=2,
            soil_type="Loamy", irrigation="Rain",
        )
        listing = FarmerService.create_produce_listing(
            user=farmer, category="GRAINS", title="Rice", price=Decimal("50"),
            unit_of_measure="kg", available_stock=100, description="Fresh rice",
        )
        proposal = BuyerService.submit_proposal(
            user=buyer, listing_id=listing.pk, quantity=10,
            offered_price=Decimal("45"), note="Bulk purchase",
        )
        self.assertEqual(proposal.farmer_id, farmer.pk)
        self.assertEqual(proposal.buyer_id, buyer.pk)
        accepted = FarmerService.respond_to_trade_proposal(
            user=farmer, proposal_id=proposal.pk, action="ACCEPT",
        )
        self.assertEqual(accepted.status, "ACCEPTED")
        token = FarmerService.generate_trade_token(user=farmer, proposal_id=proposal.pk)
        self.assertTrue(token)
        self.assertEqual(DirectTradeProposal.objects.get(pk=proposal.pk).security_token, token)

    def test_seller_inventory_and_order_workflow(self):
        seller = self._user("seller", User.Role.SELLER)
        farmer = self._user("input-farmer", User.Role.FARMER)
        profile = SellerService.create_profile(
            user=seller, shop_name="Agri Shop", license_number="LIC123456",
            gst_number="22AAAAA0000A1Z5", description="Input store",
        )
        self.assertEqual(profile.shop_name, "Agri Shop")
        listing = SellerService.create_listing(
            user=seller, category="SEEDS", title="Paddy Seeds", price=Decimal("100"),
            unit_of_measure="kg", available_stock=20, min_order_quantity=2,
            description="Certified seeds",
        )
        self.assertEqual(listing.wing, "INPUT")
        order = FarmerService.place_input_order(
            user=farmer, listing_id=listing.pk, quantity=2,
            payment_method="UPI", delivery_address="Pathanamthitta, Kerala",
        )
        self.assertIsInstance(order, InputOrder)
        self.assertEqual(order.status, "PENDING")
        shipped = SellerService.update_order_status(
            user=seller, order_id=order.order_id, status="SHIPPED",
        )
        self.assertEqual(shipped.status, "SHIPPED")
        delivered = SellerService.update_order_status(
            user=seller, order_id=order.order_id, status="DELIVERED",
        )
        self.assertEqual(delivered.status, "DELIVERED")
        txn = EscrowTransaction.objects.get(security_token=f"ORDER-{order.order_id}")
        self.assertEqual(txn.payment_status, "COMPLETED")

    def test_buyer_profile_and_proposal_workflow(self):
        farmer = self._user("produce-farmer", User.Role.FARMER)
        buyer = self._user("corporate-buyer", User.Role.BUYER)
        FarmerService.create_profile(
            user=farmer, aadhar_no="123456789014", land_area=3,
            soil_type="Clay", irrigation="Canal",
        )
        profile = BuyerService.create_profile(
            user=buyer, company_name="Agri Buyer Pvt Ltd",
            gst_number="22BBBBB0000B1Z5", iec_code="1234567890",
        )
        self.assertEqual(profile.company_name, "Agri Buyer Pvt Ltd")
        listing = FarmerService.create_produce_listing(
            user=farmer, category="VEGETABLES", title="Tomato", price=Decimal("40"),
            unit_of_measure="kg", available_stock=50, description="Fresh tomato",
        )
        proposal = BuyerService.submit_proposal(
            user=buyer, listing_id=listing.pk, quantity=5,
            offered_price=Decimal("35"),
        )
        rejected = BuyerService.respond_to_proposal(
            user=buyer, proposal_id=proposal.pk, action="REJECT",
        )
        self.assertEqual(rejected.status, "REJECTED")

    def test_admin_moderation_and_refund(self):
        admin = self._user("admin", User.Role.ADMIN)
        seller = self._user("moderated-seller", User.Role.SELLER)
        listing = SellerService.create_listing(
            user=seller, category="TOOLS", title="Hoe", price=Decimal("500"),
            unit_of_measure="piece", available_stock=5, description="Farm tool",
        )
        banned = AdminService.moderate_listing(
            admin=admin, listing_id=listing.pk, action="BAN",
        )
        self.assertEqual(banned.status, "BANNED")
        approved = AdminService.approve_user(admin=admin, user_id=seller.pk)
        self.assertTrue(approved.is_verified)
        self.assertTrue(approved.is_active)

    def test_admin_can_refund_locked_escrow(self):
        admin = self._user("refund-admin", User.Role.ADMIN)
        farmer = self._user("refund-farmer", User.Role.FARMER)
        buyer = self._user("refund-buyer", User.Role.BUYER)
        listing = FarmerService.create_produce_listing(
            user=farmer, category="GRAINS", title="Wheat", price=Decimal("50"),
            unit_of_measure="kg", available_stock=10, description="Wheat",
        )
        txn = EscrowTransaction.objects.create(
            item_purchased=listing, vendor=farmer, purchaser=buyer,
            amount_paid=Decimal("500"), payment_status="ESCROW_LOCKED",
        )
        refunded = AdminService.refund_escrow(
            admin=admin, transaction_id=txn.transaction_id,
        )
        self.assertEqual(refunded.payment_status, "REFUNDED")
