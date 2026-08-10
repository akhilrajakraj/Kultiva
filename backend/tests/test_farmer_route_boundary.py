import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.urls import resolve


class FarmerRouteBoundaryTests(unittest.TestCase):
    ROUTES = {
        "farmer_home": "/farmer/home",
        "farmer_profile": "/farmer/profile/",
        "submit_manual_soil": "/farmer/submit-soil-report/",
        "add_farmer_listing": "/farmer/add-listing/",
        "farmer_manage_crops": "/farmer/my-crops/",
        "edit_farmer_listing": "/farmer/edit-listing/",
        "delete_farmer_listing": "/farmer/delete-listing/1/",
        "send_trade_proposal": "/farmer/send-proposal/",
        "farmer_proposals": "/farmer/trade-contracts/",
        "farmer_proposal_detail": "/farmer/contract/1/",
        "generate_trade_qr": "/farmer/generate-qr/1/",
        "farmer_respond_proposal": "/farmer/proposal/1/respond/",
        "farmer_input_market": "/farmer/input-market/",
        "farmer_input_detail": "/farmer/input-market/product/1/",
        "farmer_checkout": "/farmer/checkout/1/",
        "process_input_order": "/farmer/process-order/1/",
        "dummy_payment_gateway": "/farmer/payment-gateway/1/",
        "farmer_orders": "/farmer/my-orders/",
        "farmer_invoice_detail": "/farmer/invoice/ORDER-1/",
        "farmer_order_details": "/farmer/orders/ORDER-1/",
        "farmer_seller_list": "/farmer/network/sellers/",
        "farmer_view_seller_profile": "/farmer/network/seller/1/",
    }

    def test_every_legacy_farmer_url_resolves_to_extracted_boundary(self):
        for route_name, path in self.ROUTES.items():
            with self.subTest(route_name=route_name):
                match = resolve(path)
                self.assertEqual(match.url_name, route_name)
                self.assertEqual(match.func.__module__, "backend.apps.farmers.views")


if __name__ == "__main__":
    unittest.main()
