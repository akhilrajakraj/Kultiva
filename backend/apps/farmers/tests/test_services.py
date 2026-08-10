from decimal import Decimal

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.farmers.services import FarmerService
from backend.core.legacy.models import FarmerProfile, MarketplaceListing


class FarmerServiceTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(
            email="farmer-service@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_active=True,
        )

    def test_create_profile_validates_and_persists_farmer_profile(self):
        profile = FarmerService.create_profile(
            user=self.farmer,
            aadhar_no="123456789012",
            land_area=2.5,
            soil_type="Loamy",
            irrigation="Drip",
        )
        self.assertEqual(profile.user, self.farmer)
        self.assertEqual(profile.aadhar_no, "123456789012")
        self.assertTrue(FarmerProfile.objects.filter(user=self.farmer).exists())

    def test_create_profile_rejects_duplicate_profile(self):
        FarmerProfile.objects.create(
            user=self.farmer,
            aadhar_no="123456789012",
            land_area=1,
            soil_type="Loamy",
            irrigation="Drip",
        )
        with self.assertRaisesMessage(ValueError, "A farmer profile already exists"):
            FarmerService.create_profile(
                user=self.farmer,
                aadhar_no="123456789012",
                land_area=1,
                soil_type="Loamy",
                irrigation="Drip",
            )

    def test_create_listing_rejects_non_positive_price(self):
        with self.assertRaisesMessage(ValueError, "Price and stock must be greater than zero"):
            FarmerService.create_produce_listing(
                user=self.farmer,
                category="Vegetables",
                title="Tomato",
                price=Decimal("0"),
                unit_of_measure="kg",
                available_stock=10,
                min_order_quantity=1,
                description="Fresh tomatoes",
            )

    def test_create_listing_persists_produce_listing(self):
        listing = FarmerService.create_produce_listing(
            user=self.farmer,
            category="Vegetables",
            title="Tomato",
            price=Decimal("40"),
            unit_of_measure="kg",
            available_stock=10,
            min_order_quantity=2,
            description="Fresh tomatoes",
        )
        self.assertEqual(listing.listed_by, self.farmer)
        self.assertEqual(listing.wing, "PRODUCE")
        self.assertEqual(listing.price, Decimal("40"))
        self.assertEqual(listing.status, "ACTIVE")

    def test_non_farmer_cannot_use_farmer_service(self):
        buyer = User.objects.create_user(
            email="buyer-service@example.com",
            password="test-password",
            role=User.Role.BUYER,
            is_active=True,
        )
        with self.assertRaisesMessage(ValueError, "Only users with the FARMER role"):
            FarmerService.list_inventory(user=buyer)
