from decimal import Decimal

from django.test import TestCase

from backend.apps.marketplace.services import MarketplaceService
from backend.apps.orders.services import OrderService
from backend.core.legacy.models import InputOrder, MarketplaceListing
from backend.core.legacy.models import User


class MarketplaceOrderExtractionTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(username="farmer1", password="x", role=User.Role.FARMER, is_active=True)
        self.seller = User.objects.create_user(username="seller1", password="x", role=User.Role.SELLER, is_active=True)
        self.buyer = User.objects.create_user(username="buyer1", password="x", role=User.Role.BUYER, is_active=True)

    def test_create_and_browse_produce_listing(self):
        listing = MarketplaceService.create_listing(
            user=self.farmer,
            wing="PRODUCE",
            category="VEGETABLES",
            title="Fresh Tomato",
            price=Decimal("80.00"),
            unit_of_measure="kg",
            available_stock=100,
            min_order_quantity=5,
            description="Grade A tomatoes",
            is_organic=True,
        )
        results = MarketplaceService.browse(user=self.buyer, query="tomato", organic=True)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().pk, listing.pk)

    def test_listing_update_rejects_invalid_minimum(self):
        listing = MarketplaceService.create_listing(
            user=self.farmer,
            wing="PRODUCE",
            category="FRUITS",
            title="Mango",
            price=100,
            unit_of_measure="kg",
            available_stock=20,
            min_order_quantity=2,
            description="Alphonso",
        )
        with self.assertRaises(ValueError):
            MarketplaceService.update_listing(user=self.farmer, listing_id=listing.pk, changes={"min_order_quantity": 30})

    def test_input_order_is_atomic_and_decrements_stock(self):
        product = MarketplaceService.create_listing(
            user=self.seller,
            wing="INPUT",
            category="SEEDS",
            title="Rice Seeds",
            price=Decimal("50.00"),
            unit_of_measure="kg",
            available_stock=20,
            min_order_quantity=2,
            description="Certified seed",
        )
        order = OrderService.place_input_order(
            user=self.farmer,
            listing_id=product.pk,
            quantity=5,
            payment_method="UPI",
            delivery_address="Village, District, Kerala - 689000",
        )
        product.refresh_from_db()
        self.assertIsInstance(order, InputOrder)
        self.assertEqual(product.available_stock, 15)
        self.assertEqual(order.total_amount, Decimal("270.00"))

    def test_input_order_rejects_insufficient_stock(self):
        product = MarketplaceService.create_listing(
            user=self.seller,
            wing="INPUT",
            category="TOOLS",
            title="Hand Tool",
            price=100,
            unit_of_measure="unit",
            available_stock=2,
            min_order_quantity=1,
            description="Farm tool",
        )
        with self.assertRaises(ValueError):
            OrderService.place_input_order(
                user=self.farmer,
                listing_id=product.pk,
                quantity=3,
                payment_method="CARD",
                delivery_address="Address",
            )
        product.refresh_from_db()
        self.assertEqual(product.available_stock, 2)
