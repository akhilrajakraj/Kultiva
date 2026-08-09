import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.test import Client, TestCase
from django.urls import resolve

from backend.apps.accounts.models import User
from backend.core.legacy.models import DirectTradeProposal, EscrowTransaction, MarketplaceListing


class EscrowLegacyViewIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farmer = User.objects.create_user(
            username="legacy-farmer",
            email="legacy-farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_active=True,
        )
        self.buyer = User.objects.create_user(
            username="legacy-buyer",
            email="legacy-buyer@example.com",
            password="test-password",
            role=User.Role.BUYER,
            is_active=True,
        )
        self.listing = MarketplaceListing.objects.create(
            listed_by=self.farmer,
            wing="PRODUCE",
            category="GRAINS",
            title="Legacy Integration Rice",
            description="Escrow integration test listing",
            price=Decimal("80.00"),
            unit_of_measure="kg",
            available_stock=100,
            min_order_quantity=10,
        )
        self.proposal = DirectTradeProposal.objects.create(
            listing=self.listing,
            farmer=self.farmer,
            buyer=self.buyer,
            status="ACCEPTED",
            requested_quantity=10,
            proposed_price=Decimal("75.00"),
            total_amount=Decimal("750.00"),
            security_token="legacy-test-token",
        )

    def test_legacy_escrow_routes_resolve_to_adapter_module(self):
        checkout = resolve(f"/buyer/escrow-checkout/{self.proposal.pk}/")
        fund = resolve(f"/buyer/escrow/{self.proposal.pk}/fund/")
        refund = resolve(f"/buyer/escrow/{self.proposal.pk}/refund/")

        self.assertEqual(checkout.func.__module__, "backend.apps.escrow.legacy_views")
        self.assertEqual(fund.func.__module__, "backend.apps.escrow.legacy_views")
        self.assertEqual(refund.func.__module__, "backend.apps.escrow.legacy_views")

    def test_fund_endpoint_uses_negotiated_amount_and_locks_escrow(self):
        self.client.force_login(self.buyer)

        response = self.client.post(
            f"/buyer/escrow/{self.proposal.pk}/fund/",
        )

        self.assertEqual(response.status_code, 302)
        escrow = EscrowTransaction.objects.get(
            purchaser=self.buyer,
            item_purchased=self.listing,
        )
        self.assertEqual(escrow.amount_paid, Decimal("750.00"))
        self.assertEqual(escrow.payment_status, "ESCROW_LOCKED")
        self.proposal.refresh_from_db()
        self.assertFalse(self.proposal.is_paid)

    def test_fund_endpoint_is_idempotent(self):
        self.client.force_login(self.buyer)

        self.client.post(f"/buyer/escrow/{self.proposal.pk}/fund/")
        self.client.post(f"/buyer/escrow/{self.proposal.pk}/fund/")

        self.assertEqual(
            EscrowTransaction.objects.filter(
                purchaser=self.buyer,
                item_purchased=self.listing,
            ).count(),
            1,
        )

    def test_other_buyer_cannot_fund_the_proposal(self):
        other_buyer = User.objects.create_user(
            username="unauthorized-buyer",
            email="unauthorized@example.com",
            password="test-password",
            role=User.Role.BUYER,
            is_active=True,
        )
        self.client.force_login(other_buyer)

        response = self.client.post(f"/buyer/escrow/{self.proposal.pk}/fund/")

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            EscrowTransaction.objects.filter(
                purchaser=other_buyer,
                item_purchased=self.listing,
            ).exists()
        )

    def test_process_payment_completes_service_escrow_and_preserves_negotiated_amount(self):
        self.client.force_login(self.buyer)

        response = self.client.post(
            f"/buyer/process-payment/{self.proposal.pk}/",
        )

        self.assertEqual(response.status_code, 302)
        escrow = EscrowTransaction.objects.get(
            purchaser=self.buyer,
            item_purchased=self.listing,
        )
        self.assertEqual(escrow.amount_paid, Decimal("750.00"))
        self.assertEqual(escrow.payment_status, "COMPLETED")

        self.proposal.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertTrue(self.proposal.is_paid)
        self.assertEqual(self.listing.available_stock, 0)
        self.assertEqual(self.listing.status, "OUT_OF_STOCK")
