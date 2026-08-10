import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from decimal import Decimal

from django.test import Client, TestCase
from django.urls import resolve

from backend.apps.accounts.models import User
from backend.apps.admin_portal.services import AdminService
from backend.core.legacy.models import EscrowTransaction, ManualSoilReport, MarketplaceListing


class AdminLegacyViewIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin-integration",
            email="admin-integration@example.com",
            password="test-password",
            role=User.Role.ADMIN,
            is_active=True,
            is_verified=True,
        )
        self.farmer = User.objects.create_user(
            username="pending-farmer",
            email="pending-farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_active=False,
            is_verified=False,
        )
        self.seller = User.objects.create_user(
            username="admin-seller",
            email="admin-seller@example.com",
            password="test-password",
            role=User.Role.SELLER,
            is_active=True,
            is_verified=True,
        )
        self.listing = MarketplaceListing.objects.create(
            listed_by=self.seller,
            wing="INPUT",
            category="SEEDS",
            title="Admin Moderation Seed",
            description="Moderation fixture",
            price=Decimal("100.00"),
            unit_of_measure="kg",
            available_stock=10,
            min_order_quantity=1,
            status="ACTIVE",
        )

    def test_admin_mutation_routes_resolve_to_extracted_views(self):
        expected = {
            "approve_user": f"/approve/{self.farmer.pk}/",
            "farmer_action": "/admin/farmer-action/",
            "buyer_action": "/admin/buyer-action/",
            "seller_action": "/admin/seller-action/",
            "process_b2b_refund": "/custom-admin/refunds/b2b/process/NO-TXN/",
            "process_b2c_refund": "/custom-admin/refunds/b2c/process/NO-ORDER/",
            "takedown_product": f"/custom-admin/products/takedown/{self.listing.pk}/",
            "update_soil_report": "/custom-admin/update-soil-report/",
        }
        for name, path in expected.items():
            match = resolve(path)
            self.assertEqual(match.url_name, name)
            self.assertEqual(match.func.__module__, "backend.apps.admin_portal.views")

    def test_approve_user_uses_admin_service_boundary(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/approve/{self.farmer.pk}/")
        self.assertEqual(response.status_code, 302)
        self.farmer.refresh_from_db()
        self.assertTrue(self.farmer.is_active)
        self.assertTrue(self.farmer.is_verified)

    def test_non_admin_cannot_approve_user(self):
        self.client.force_login(self.seller)
        response = self.client.get(f"/approve/{self.farmer.pk}/")
        self.assertEqual(response.status_code, 302)
        self.farmer.refresh_from_db()
        self.assertFalse(self.farmer.is_active)
        self.assertFalse(self.farmer.is_verified)

    def test_takedown_uses_admin_service_and_bans_listing(self):
        self.client.force_login(self.admin)
        response = self.client.post(f"/custom-admin/products/takedown/{self.listing.pk}/")
        self.assertEqual(response.status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "BANNED")

    def test_admin_service_rejects_self_suspension(self):
        with self.assertRaisesMessage(ValueError, "An administrator cannot suspend their own account."):
            AdminService.suspend_user(admin=self.admin, user_id=self.admin.pk)

    def test_admin_service_rejects_non_admin_mutation(self):
        with self.assertRaisesMessage(PermissionError, "Administrator privileges are required."):
            AdminService.approve_user(admin=self.seller, user_id=self.farmer.pk)
