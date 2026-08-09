from decimal import Decimal

from django.test import TestCase

from backend.apps.marketplace.services import MarketplaceService
from backend.apps.orders.services import OrderService
from backend.apps.sellers.services import SellerService
from backend.core.legacy.models import InputOrder, MarketplaceListing
from backend.core.legacy.models import User


class MarketplaceOrderExtractionTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(username="farmer1", password="x", role=User.Role.FARMER, is_active=True)
        self.seller = User.objects.create_user(username="seller1", password="x", role=User.Role.SELLER, is_active=True)
        self.seller.is_verified = True
        self.seller.save(update_fields=["is_verified"])
        self.other_seller = User.objects.create_user(username="seller2", password="x", role=User.Role.SELLER, is_active=True)
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

    def _input_product(self, stock=20):
        return MarketplaceService.create_listing(
            user=self.seller,
            wing="INPUT",
            category="SEEDS",
            title="Rice Seeds",
            price=Decimal("50.00"),
            unit_of_measure="kg",
            available_stock=stock,
            min_order_quantity=2,
            description="Certified seed",
        )

    def test_seller_service_lists_only_owned_inventory(self):
        own = self._input_product()
        MarketplaceService.create_listing(
            user=self.other_seller,
            wing="INPUT",
            category="TOOLS",
            title="Other Seller Tool",
            price=100,
            unit_of_measure="unit",
            available_stock=5,
            min_order_quantity=1,
            description="Tool",
        )
        listings = SellerService.list_inventory(user=self.seller)
        self.assertEqual(list(listings.values_list("pk", flat=True)), [own.pk])

    def test_unverified_seller_cannot_publish_inventory(self):
        self.seller.is_verified = False
        self.seller.save(update_fields=["is_verified"])
        with self.assertRaises(ValueError):
            SellerService.create_listing(
                user=self.seller,
                category="SEEDS",
                title="Blocked Seeds",
                price=50,
                unit_of_measure="kg",
                available_stock=5,
                min_order_quantity=1,
                description="Should not publish",
            )

    def test_seller_service_rejects_cross_seller_listing_access(self):
        product = self._input_product()
        with self.assertRaises(MarketplaceListing.DoesNotExist):
            SellerService.get_listing(user=self.other_seller, listing_id=product.pk)
        with self.assertRaises(MarketplaceListing.DoesNotExist):
            SellerService.update_listing(user=self.other_seller, listing_id=product.pk, changes={"title": "Hijacked"})

    def test_input_order_is_atomic_and_decrements_stock(self):
        product = self._input_product()
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

    def test_seller_can_update_owned_order_status(self):
        product = self._input_product()
        order = OrderService.place_input_order(
            user=self.farmer,
            listing_id=product.pk,
            quantity=2,
            payment_method="CARD",
            delivery_address="Address",
        )
        updated = SellerService.update_order_status(user=self.seller, order_id=order.order_id, status="SHIPPED")
        self.assertEqual(updated.status, "SHIPPED")

    def test_seller_cannot_update_another_sellers_order(self):
        product = self._input_product()
        order = OrderService.place_input_order(
            user=self.farmer,
            listing_id=product.pk,
            quantity=2,
            payment_method="COD",
            delivery_address="Address",
        )
        with self.assertRaises(ValueError):
            SellerService.update_order_status(user=self.other_seller, order_id=order.order_id, status="SHIPPED")

    def test_terminal_order_status_cannot_be_reopened(self):
        product = self._input_product()
        order = OrderService.place_input_order(
            user=self.farmer,
            listing_id=product.pk,
            quantity=2,
            payment_method="UPI",
            delivery_address="Address",
        )
        SellerService.update_order_status(user=self.seller, order_id=order.order_id, status="SHIPPED")
        SellerService.update_order_status(user=self.seller, order_id=order.order_id, status="DELIVERED")
        with self.assertRaises(ValueError):
            SellerService.update_order_status(user=self.seller, order_id=order.order_id, status="SHIPPED")
