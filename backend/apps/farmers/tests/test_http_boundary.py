from django.test import SimpleTestCase

from backend.apps.farmers import views


class FarmerHttpBoundaryTests(SimpleTestCase):
    def test_farmer_boundary_exposes_expected_workflows(self):
        expected = {
            "profile",
            "add_listing",
            "manage_crops",
            "edit_listing",
            "delete_listing",
            "submit_soil_report",
            "proposals",
            "proposal_detail",
            "send_proposal",
            "respond_proposal",
            "generate_trade_qr",
            "input_market",
            "input_detail",
            "checkout",
            "process_order",
            "payment_gateway",
            "orders",
            "order_detail",
            "invoice_detail",
        }
        self.assertTrue(expected.issubset(set(views.__all__)))
