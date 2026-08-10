import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal

from django.test import TestCase
from django.urls import resolve

from backend.apps.accounts.models import User
from backend.apps.admin_portal.services import AdminService
from backend.core.legacy.models import EscrowTransaction, MarketplaceListing, ManualSoilReport


class AdminPortalExtractionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="extracted-admin",
            email="admin@example.com",
            password="test-password",
            role=User.Role.ADMIN,
            is_active=True,
        )
        self.farmer = User.objects.create_user(
            username="pending-farmer",
            email="farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_active=True,
            is_verified=False,
        )
        self.seller = User.objects.create_user(
            username="admin-seller",
            email="seller@example.com",
            password="test-password",
            role=User.Role.SELLER,
            is_active=True,
            is_verified=True,
        )
        self.buyer = User.objects.create_user(
            username="admin-buyer",
            email="buyer@example.com",
            password="test-password",
            role=User.Role.BUYER,
            is_active=True,
            is_verified=True,
        )
        self.listing = MarketplaceListing.objects.create(
            listed_by=self.seller,
            wing="INPUT",
            category="SEEDS",
            title="Admin Moderation Seed",
            description="Seed listing",
            price=Decimal("100.00"),
            unit_of_measure="kg",
            available_stock=20,
            min_order_quantity=2,
            status="ACTIVE",
        )

    def test_admin_can_approve_user(self):
        updated = AdminService.approve_user(admin=self.admin, user_id=self.farmer.pk)
        self.assertTrue(updated.is_verified)
        self.assertTrue(updated.is_active)

    def test_non_admin_cannot_approve_user(self):
        with self.assertRaisesMessage(PermissionError, "Administrator privileges are required."):
            AdminService.approve_user(admin=self.buyer, user_id=self.farmer.pk)

    def test_admin_can_suspend_another_user_but_not_self(self):
        updated = AdminService.suspend_user(admin=self.admin, user_id=self.farmer.pk)
        self.assertFalse(updated.is_active)

        with self.assertRaisesMessage(ValueError, "An administrator cannot suspend their own account."):
            AdminService.suspend_user(admin=self.admin, user_id=self.admin.pk)

    def test_listing_moderation_ban_is_atomic_state_change(self):
        listing = AdminService.moderate_listing(
            admin=self.admin,
            listing_id=self.listing.pk,
            action="BAN",
        )
        self.assertEqual(listing.status, "BANNED")

    def test_empty_listing_cannot_be_reactivated(self):
        self.listing.available_stock = 0
        self.listing.save(update_fields=["available_stock"])
        with self.assertRaisesMessage(ValueError, "An empty listing cannot be activated."):
            AdminService.moderate_listing(
                admin=self.admin,
                listing_id=self.listing.pk,
                action="ACTIVATE",
            )

    def test_admin_can_complete_manual_soil_report(self):
        report = ManualSoilReport.objects.create(farmer=self.farmer, request_status="PENDING")
        updated = AdminService.update_soil_report(
            admin=self.admin,
            report_id=report.pk,
            status="COMPLETED",
            nitrogen=40,
            phosphorus=20,
            potassium=30,
            ph=6.5,
        )
        self.assertEqual(updated.request_status, "COMPLETED")
        self.assertEqual(updated.n, 40)
        self.assertEqual(updated.ph, 6.5)

    def test_admin_can_refund_locked_escrow_only(self):
        escrow = EscrowTransaction.objects.create(
            item_purchased=self.listing,
            vendor=self.seller,
            purchaser=self.buyer,
            amount_paid=Decimal("200.00"),
            payment_status="ESCROW_LOCKED",
        )
        updated = AdminService.refund_escrow(
            admin=self.admin,
            transaction_id=escrow.transaction_id,
        )
        self.assertEqual(updated.payment_status, "REFUNDED")

    def test_admin_cannot_refund_completed_escrow(self):
        escrow = EscrowTransaction.objects.create(
            item_purchased=self.listing,
            vendor=self.seller,
            purchaser=self.buyer,
            amount_paid=Decimal("200.00"),
            payment_status="COMPLETED",
        )
        with self.assertRaisesMessage(ValueError, "Only locked escrow funds can be refunded."):
            AdminService.refund_escrow(
                admin=self.admin,
                transaction_id=escrow.transaction_id,
            )
