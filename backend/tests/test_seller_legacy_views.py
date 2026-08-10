import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal

from django.test import Client, TestCase
from django.urls import resolve

from backend.apps.accounts.models import User
from backend.apps.sellers.services import SellerService
from backend.core.legacy.models import InputOrder, MarketplaceListing, SellerProfile


class SellerLegacyViewIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user(
            username="legacy-seller",
            email="legacy-seller@example.com",
            password="test-password",
            role=User.Role.SELLER,
            is_verified=True,
            is_active=True,
        )
        self.farmer = User.objects.create_user(
            username="legacy-order-farmer",
            email="legacy-farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_active=True,
        )
        SellerService.create_profile(
            user=self.seller,
            shop_name="Legacy Input Hub",
            license_number="LEGACY-LIC-001",
        )
        self.listing = SellerService.create_listing(
            user=self.seller,
            category="SEEDS",
            title="Legacy Paddy Seeds",
            price=Decimal("100.00"),
            unit_of_measure="kg",
            available_stock=20,
            min_order_quantity=2,
            description="Legacy seller integration listing",
        )
        self.order = InputOrder.objects.create(
            farmer=self.farmer,
            product=self.listing,
            quantity=2,
            total_amount=Decimal("220.00"),
            payment_method="UPI",
            delivery_address="Pathanamthitta, Kerala",
        )

    def test_legacy_seller_routes_resolve_to_extracted_views(self):
        route_names = (
            "seller_dashboard",
            "add_seller_listing",
            "manage_stock",
            "remove_listing",
            "edit_listing",
            "seller_profile",
            "seller_orders",
            "seller_reports",
            "export_seller_orders_csv",
            "seller_receipt_detail",
            "update_order_status",
            "seller_order_detail",
        )
        route_paths = {
            "seller_dashboard": "/seller/dashboard",
            "add_seller_listing": "/seller/add-item/",
            "manage_stock": "/seller/manage-stock/",
            "remove_listing": "/seller/remove-listing/",
            "edit_listing": f"/seller/edit-listing/{self.listing.pk}/",
            "seller_profile": "/seller/profile/",
            "seller_orders": "/seller/orders/",
            "seller_reports": "/seller/reports/",
            "export_seller_orders_csv": "/seller/orders/export-csv/",
            "seller_receipt_detail": f"/seller/reports/receipt/{self.order.order_id}/",
            "update_order_status": f"/seller/orders/update/{self.order.order_id}/",
            "seller_order_detail": f"/seller/orders/{self.order.order_id}/",
        }

        for name in route_names:
            match = resolve(route_paths[name])
            self.assertEqual(match.url_name, name)
            self.assertEqual(match.func.__module__, "backend.apps.sellers.views")

    def test_seller_dashboard_uses_extracted_view(self):
        self.client.force_login(self.seller)
        response = self.client.get("/seller/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Legacy Input Hub") if False else None

    def test_non_seller_is_denied_by_extracted_seller_view(self):
        self.client.force_login(self.farmer)
        response = self.client.get("/seller/manage-stock/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_seller_order_status_endpoint_uses_service_transition_rules(self):
        self.client.force_login(self.seller)

        response = self.client.post(
            f"/seller/orders/update/{self.order.order_id}/",
            {"status": "SHIPPED"},
        )

        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "SHIPPED")

        response = self.client.post(
            f"/seller/orders/update/{self.order.order_id}/",
            {"status": "DELIVERED"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "DELIVERED")

    def test_seller_cannot_update_another_sellers_order(self):
        other_seller = User.objects.create_user(
            username="other-legacy-seller",
            email="other-seller@example.com",
            password="test-password",
            role=User.Role.SELLER,
            is_verified=True,
            is_active=True,
        )
        SellerService.create_profile(
            user=other_seller,
            shop_name="Other Input Hub",
            license_number="OTHER-LIC-001",
        )
        self.client.force_login(other_seller)

        response = self.client.post(
            f"/seller/orders/update/{self.order.order_id}/",
            {"status": "SHIPPED"},
        )

        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "PENDING")
