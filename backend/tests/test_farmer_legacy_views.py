import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal

from django.test import Client, TestCase
from django.urls import resolve

from backend.apps.accounts.models import User
from backend.apps.farmers.services import FarmerService
from backend.core.legacy.models import MarketplaceListing


class FarmerLegacyViewIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farmer = User.objects.create_user(
            username="legacy-farmer",
            email="legacy-farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_verified=True,
            is_active=True,
        )
        self.seller = User.objects.create_user(
            username="legacy-input-seller",
            email="legacy-seller@example.com",
            password="test-password",
            role=User.Role.SELLER,
            is_verified=True,
            is_active=True,
        )
        FarmerService.create_profile(
            user=self.farmer,
            aadhar_no="999999999999",
            land_area=2.0,
            soil_type="Loamy",
            irrigation="Rain",
        )
        self.produce = FarmerService.create_produce_listing(
            user=self.farmer,
            category="VEGETABLES",
            title="Legacy Tomatoes",
            price=Decimal("40.00"),
            unit_of_measure="kg",
            available_stock=10,
            min_order_quantity=1,
            description="Fresh legacy produce",
        )
        self.input_product = MarketplaceListing.objects.create(
            listed_by=self.seller,
            wing="INPUT",
            category="SEEDS",
            title="Legacy Paddy Seeds",
            price=Decimal("100.00"),
            unit_of_measure="kg",
            available_stock=10,
            min_order_quantity=2,
            description="Certified seeds",
            status="ACTIVE",
        )

    def test_all_extracted_farmer_routes_resolve_to_domain_views(self):
        route_paths = {
            "farmer_profile": "/farmer/profile/",
            "add_farmer_listing": "/farmer/add-listing/",
            "farmer_manage_crops": "/farmer/my-crops/",
            "edit_farmer_listing": "/farmer/edit-listing/",
            "delete_farmer_listing": f"/farmer/delete-listing/{self.produce.pk}/",
            "submit_manual_soil": "/farmer/submit-soil-report/",
            "send_trade_proposal": "/farmer/send-proposal/",
            "farmer_proposals": "/farmer/trade-contracts/",
            "farmer_proposal_detail": "/farmer/contract/1/",
            "farmer_respond_proposal": "/farmer/proposal/1/respond/",
            "generate_trade_qr": "/farmer/generate-qr/1/",
            "farmer_input_market": "/farmer/input-market/",
            "farmer_input_detail": f"/farmer/input-market/product/{self.input_product.pk}/",
            "farmer_checkout": f"/farmer/checkout/{self.input_product.pk}/",
            "process_input_order": f"/farmer/process-order/{self.input_product.pk}/",
            "dummy_payment_gateway": f"/farmer/payment-gateway/{self.input_product.pk}/",
            "farmer_orders": "/farmer/my-orders/",
            "farmer_invoice_detail": "/farmer/invoice/ORDER-TEST/",
            "farmer_order_details": "/farmer/orders/ORDER-TEST/",
        }

        for name, path in route_paths.items():
            match = resolve(path)
            self.assertEqual(match.url_name, name)
            self.assertEqual(match.func.__module__, "backend.apps.farmers.views")

    def test_farmer_manage_crops_uses_extracted_view(self):
        self.client.force_login(self.farmer)
        response = self.client.get("/farmer/my-crops/")
        self.assertEqual(response.status_code, 200)

    def test_non_farmer_is_denied_by_extracted_farmer_view(self):
        self.client.force_login(self.seller)
        response = self.client.get("/farmer/my-crops/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_add_listing_delegates_creation_to_farmer_service(self):
        self.client.force_login(self.farmer)
        response = self.client.post(
            "/farmer/add-listing/",
            {
                "category": "FRUITS",
                "title": "Mangoes",
                "price": "80",
                "unit_of_measure": "kg",
                "available_stock": "25",
                "min_order_quantity": "2",
                "description": "Fresh mangoes",
                "variety_or_brand": "Alphonso",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            MarketplaceListing.objects.filter(
                listed_by=self.farmer,
                wing="PRODUCE",
                title="Mangoes",
            ).exists()
        )

    def test_input_order_route_delegates_to_farmer_service(self):
        self.client.force_login(self.farmer)
        response = self.client.post(
            f"/farmer/process-order/{self.input_product.pk}/",
            {"quantity": "2", "payment_mode": "UPI"},
        )
        self.assertEqual(response.status_code, 302)
        self.input_product.refresh_from_db()
        self.assertEqual(self.input_product.available_stock, 8)

    def test_farmer_cannot_modify_another_farmers_listing(self):
        other_farmer = User.objects.create_user(
            username="other-legacy-farmer",
            email="other-farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_verified=True,
            is_active=True,
        )
        FarmerService.create_profile(
            user=other_farmer,
            aadhar_no="888888888888",
            land_area=1.0,
            soil_type="Clay",
            irrigation="Canal",
        )
        self.client.force_login(other_farmer)
        response = self.client.post(
            "/farmer/edit-listing/",
            {"listing_id": str(self.produce.pk), "price": "1"},
        )
        self.assertEqual(response.status_code, 302)
        self.produce.refresh_from_db()
        self.assertEqual(self.produce.price, Decimal("40.00"))
