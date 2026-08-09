from decimal import Decimal

from django.test import TestCase

from backend.apps.marketplace.services import MarketplaceService
from backend.apps.orders.services import OrderService
from backend.apps.sellers.services import SellerService
from backend.core.legacy.models import InputOrder, MarketplaceListing, User


class MarketplaceOrderExtractionTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(username="farmer1", password="x", role=User.Role.FARMER, is_active=True)
        self.seller = User.objects.create_user(username="seller1", password="x", role=User.Role.SELLER, is_active=True, is_verified=True)
        self.other_seller = User.objects.create_user(username="seller2", password="x", role=User.Role.SELLER, is_active=True, is_verified=True)
        self.buyer = User.objects.create_user(username="buyer1", password="x", role=User.Role.BUYER, is_active=True)

    def _produce_product(self, stock=20):
        return MarketplaceService.create_listing(
            user=self.farmer,
            wing="PRODUCE",
            category="VEGETABLES",
            title="Fresh Tomato",
            price=Decimal("80.00"),
            unit_of_measure="kg",
            available_stock=stock,
            min_order_quantity=2,
            description="Grade A tomatoes",
            is_organic=True,
        )

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

    def test_create_and_browse_produce_listing(self):
        listing = self._produce_product(100)
        results = MarketplaceService.browse(user=self.buyer, query="tomato", organic=True)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().pk, listing.pk)

    def test_invalid_listing_input_is_rejected(self):
        with self.assertRaises(ValueError):
            MarketplaceService.create_listing(
                user=self.farmer,
                wing="PRODUCE",
                category="",
                title="Tomato",
                price=Decimal("80"),
                unit_of_measure="kg",
                available_stock=10,
                min_order_quantity=1,
                description="Grade A",
            )
        with self.assertRaises(ValueError):
            MarketplaceService.create_listing(
                user=self.farmer,
                wing="PRODUCE",
                category="VEGETABLES",
                title="Tomato",
                price="not-a-price",
                unit_of_measure="kg",
                available_stock=10,
                min_order_quantity=1,
                description="Grade A",
            )

    def test_listing_update_rejects_invalid_minimum(self):
        listing = self._produce_product()
        with self.assertRaises(ValueError):
            MarketplaceService.update_listing(
                user=self.farmer,
                listing_id=listing.pk,
                changes={"min_order_quantity": 30},
            )

    def test_listing_owner_cannot_be_crossed(self):
        listing = self._produce_product()
        with self.assertRaises(MarketplaceListing.DoesNotExist):
            MarketplaceService.update_listing(
                user=self.buyer,
                listing_id=listing.pk,
                changes={"title": "Hijacked"},
            )
        with self.assertRaises(MarketplaceListing.DoesNotExist):
            MarketplaceService.delete_listing(user=self.buyer, listing_id=listing.pk)

    def test_zero_stock_moves_listing_to_out_of_stock(self):
        listing = self._produce_product()
        MarketplaceService.update_listing(
            user=self.farmer,
            listing_id=listing.pk,
            changes={"available_stock": 0},
        )
        listing.refresh_from_db()
        self.assertEqual(listing.available_stock, 0)
        self.assertEqual(listing.status, MarketplaceService.OUT_OF_STOCK)

    def test_out_of_stock_listing_can_be_restocked(self):
        listing = self._produce_product()
        MarketplaceService.update_listing(
            user=self.farmer,
            listing_id=listing.pk,
            changes={"available_stock": 10},
        )
        listing.refresh_from_db()
        self.assertEqual(listing.available_stock, 10)
        self.assertEqual(listing.status, MarketplaceService.ACTIVE)

    def test_seller_listing_requires_verification(self):
        self.seller.is_verified = False
        self.seller.save(update_fields=["is_verified"])
        with self.assertRaises(ValueError):
            SellerService.create_listing(
                user=self.seller,
                category="SEEDS",
                title="Rice Seeds",
                price=50,
                unit_of_measure="kg",
                available_stock=10,
                min_order_quantity=1,
                description="Certified seed",
            )

    def test_seller_listing_uses_marketplace_boundary(self):
        listing = SellerService.create_listing(
            user=self.seller,
            category="SEEDS",
            title="Certified Rice Seeds",
            price=Decimal("50"),
            unit_of_measure="kg",
            available_stock=20,
            min_order_quantity=2,
            description="Certified seed",
        )
        self.assertEqual(listing.wing, MarketplaceService.INPUT)
        self.assertEqual(MarketplaceService.browse(user=self.buyer, wing=MarketplaceService.INPUT).first().pk, listing.pk)

    def test_seller_cannot_edit_another_sellers_listing(self):
        listing = self._input_product()
        with self.assertRaises(MarketplaceListing.DoesNotExist):
            SellerService.update_listing(
                user=self.other_seller,
                listing_id=listing.pk,
                changes={"title": "Hijacked input"},
            )

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
        updated = OrderService.update_status(actor=self.seller, order_id=order.order_id, status="SHIPPED")
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
            OrderService.update_status(actor=self.other_seller, order_id=order.order_id, status="SHIPPED")

    def test_terminal_order_status_cannot_be_reopened(self):
        product = self._input_product()
        order = OrderService.place_input_order(
            user=self.farmer,
            listing_id=product.pk,
            quantity=2,
            payment_method="UPI",
            delivery_address="Address",
        )
        OrderService.update_status(actor=self.seller, order_id=order.order_id, status="SHIPPED")
        OrderService.update_status(actor=self.seller, order_id=order.order_id, status="DELIVERED")
        with self.assertRaises(ValueError):
            OrderService.update_status(actor=self.seller, order_id=order.order_id, status="SHIPPED")
