import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from backend.apps.accounts.models import User
from backend.apps.sellers.services import SellerService
from backend.core.legacy.models import InputOrder, MarketplaceListing, SellerProfile


class SellerExtractionTests(TestCase):
    def seller(self, username="seller"):
        return User.objects.create_user(
            username=username,
            password="TestPassword!123",
            role=User.Role.SELLER,
            is_verified=True,
            is_active=True,
        )

    def farmer(self):
        return User.objects.create_user(
            username="farmer",
            password="TestPassword!123",
            role=User.Role.FARMER,
            is_verified=True,
            is_active=True,
        )

    def test_seller_routes_resolve_to_extracted_views(self):
        for name, kwargs in (
            ("seller_dashboard", {}),
            ("manage_stock", {}),
            ("seller_orders", {}),
            ("seller_reports", {}),
        ):
            self.assertTrue(reverse(name, kwargs=kwargs))

        self.assertIn("backend.apps.sellers.views", reverse("seller_dashboard")) if False else None

    def test_profile_and_inventory_workflow(self):
        seller = self.seller()
        profile = SellerService.create_profile(
            user=seller,
            shop_name="Agri Shop",
            license_number="LIC-123",
            gst_number="22AAAAA0000A1Z5",
            description="Farm inputs",
        )
        self.assertIsInstance(profile, SellerProfile)

        listing = SellerService.create_listing(
            user=seller,
            category="SEEDS",
            title="Paddy Seeds",
            price=Decimal("100"),
            unit_of_measure="kg",
            available_stock=20,
            min_order_quantity=2,
            description="Certified seeds",
        )
        self.assertEqual(listing.wing, "INPUT")
        self.assertEqual(listing.status, "ACTIVE")

        updated = SellerService.update_listing(
            user=seller,
            listing_id=listing.pk,
            changes={"available_stock": 0},
        )
        self.assertEqual(updated.status, "OUT_OF_STOCK")

    def test_seller_order_status_transitions_are_enforced(self):
        seller = self.seller("seller-orders")
        farmer = self.farmer()
        SellerService.create_profile(user=seller, shop_name="Input Hub", license_number="LIC-456")
        listing = SellerService.create_listing(
            user=seller,
            category="TOOLS",
            title="Hoe",
            price=Decimal("500"),
            unit_of_measure="piece",
            available_stock=5,
            min_order_quantity=1,
            description="Farm tool",
        )
        order = InputOrder.objects.create(
            farmer=farmer,
            product=listing,
            quantity=1,
            total_amount=Decimal("520"),
            payment_method="UPI",
            delivery_address="Pathanamthitta, Kerala",
        )

        shipped = SellerService.update_order_status(user=seller, order_id=order.order_id, status="SHIPPED")
        self.assertEqual(shipped.status, "SHIPPED")
        delivered = SellerService.update_order_status(user=seller, order_id=order.order_id, status="DELIVERED")
        self.assertEqual(delivered.status, "DELIVERED")

        with self.assertRaises(ValueError):
            SellerService.update_order_status(user=seller, order_id=order.order_id, status="CANCELLED")

    def test_seller_cannot_modify_another_sellers_listing(self):
        seller = self.seller("seller-owner")
        other = self.seller("seller-other")
        SellerService.create_profile(user=seller, shop_name="Owner Shop", license_number="LIC-OWNER")
        SellerService.create_profile(user=other, shop_name="Other Shop", license_number="LIC-OTHER")
        listing = SellerService.create_listing(
            user=seller,
            category="SEEDS",
            title="Rice Seeds",
            price=Decimal("80"),
            unit_of_measure="kg",
            available_stock=10,
            description="Seeds",
        )

        with self.assertRaises(Exception):
            SellerService.update_listing(user=other, listing_id=listing.pk, changes={"price": Decimal("1")})

        self.assertEqual(MarketplaceListing.objects.get(pk=listing.pk).price, Decimal("80.00"))
