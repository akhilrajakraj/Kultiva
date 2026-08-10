from django.test import SimpleTestCase
from django.urls import reverse

from backend.apps.farmers import views


class FarmerBoundaryCompatibilityTests(SimpleTestCase):
    """Protect the public farmer URL contract during boundary extraction."""

    def test_canonical_farmer_view_exports_exist(self):
        required = (
            "farmer_home", "farmer_profile_view", "submit_manual_soil",
            "add_farmer_listing", "farmer_manage_crops", "edit_farmer_listing",
            "delete_farmer_listing", "send_trade_proposal", "farmer_proposals",
            "farmer_proposal_detail", "generate_trade_qr", "farmer_respond_proposal",
            "farmer_input_market", "farmer_input_detail", "farmer_checkout",
            "process_input_order", "dummy_payment_gateway", "farmer_orders",
            "farmer_invoice_detail", "farmer_order_details", "farmer_seller_list",
            "farmer_view_seller_profile",
        )
        for name in required:
            self.assertTrue(callable(getattr(views, name, None)), name)

    def test_canonical_farmer_routes_reverse(self):
        cases = {
            "farmer_home": {}, "farmer_profile": {}, "submit_manual_soil": {},
            "add_farmer_listing": {}, "farmer_manage_crops": {},
            "edit_farmer_listing": {}, "delete_farmer_listing": {"listing_id": 1},
            "send_trade_proposal": {}, "farmer_proposals": {},
            "farmer_proposal_detail": {"proposal_id": 1},
            "generate_trade_qr": {"proposal_id": 1},
            "farmer_respond_proposal": {"proposal_id": 1},
            "farmer_input_market": {}, "farmer_input_detail": {"listing_id": 1},
            "farmer_checkout": {"listing_id": 1},
            "process_input_order": {"listing_id": 1},
            "dummy_payment_gateway": {"listing_id": 1}, "farmer_orders": {},
            "farmer_invoice_detail": {"order_id": "ORD-1"},
            "farmer_order_details": {"order_id": "ORD-1"},
            "farmer_seller_list": {}, "farmer_view_seller_profile": {"seller_id": 1},
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name):
                self.assertTrue(reverse(name, kwargs=kwargs))
