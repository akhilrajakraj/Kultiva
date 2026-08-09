import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal

from django.test import TestCase
from django.urls import resolve, reverse

from backend.apps.accounts.models import User
from backend.apps.farmers.services import FarmerService
from backend.core.legacy.models import MarketplaceListing


class FarmerExtractionTests(TestCase):
    def make_farmer(self):
        return User.objects.create_user(
            username="route-farmer",
            password="TestPassword!123",
            role=User.Role.FARMER,
            is_active=True,
            is_verified=True,
        )

    def test_extracted_route_resolves_to_domain_view(self):
        route = reverse("farmer_manage_crops")
        match = resolve(route)
        self.assertEqual(match.func.__module__, "backend.apps.farmers.views")
        self.assertEqual(match.func.__name__, "manage_crops")

    def test_listing_update_and_zero_stock_transition(self):
        farmer = self.make_farmer()
        FarmerService.create_profile(
            user=farmer,
            aadhar_no="999999999999",
            land_area=1.0,
            soil_type="Loamy",
            irrigation="Rain",
        )
        listing = FarmerService.create_produce_listing(
            user=farmer,
            category="VEGETABLES",
            title="Tomato",
            price=Decimal("40"),
            unit_of_measure="kg",
            available_stock=10,
            description="Fresh tomato",
        )
        updated = FarmerService.update_listing(
            user=farmer,
            listing_id=listing.pk,
            changes={"available_stock": 0},
        )
        self.assertEqual(updated.available_stock, 0)
        self.assertEqual(updated.status, "OUT_OF_STOCK")

    def test_input_order_is_atomic_and_decreases_stock(self):
        farmer = self.make_farmer()
        seller = User.objects.create_user(
            username="route-seller",
            password="TestPassword!123",
            role=User.Role.SELLER,
            is_active=True,
            is_verified=True,
        )
        product = MarketplaceListing.objects.create(
            listed_by=seller,
            wing="INPUT",
            category="SEEDS",
            title="Paddy Seeds",
            price=Decimal("100"),
            unit_of_measure="kg",
            available_stock=10,
            min_order_quantity=2,
            description="Certified seeds",
            status="ACTIVE",
        )
        order = FarmerService.place_input_order(
            user=farmer,
            listing_id=product.pk,
            quantity=2,
            payment_method="UPI",
            delivery_address="Pathanamthitta, Kerala",
        )
        product.refresh_from_db()
        self.assertEqual(product.available_stock, 8)
        self.assertEqual(order.payment_method, "UPI")
