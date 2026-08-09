from decimal import Decimal

from django.test import TestCase

from backend.apps.escrow.services import EscrowService
from backend.core.legacy.models import EscrowTransaction
from backend.apps.accounts.models import User
from backend.core.legacy.models import MarketplaceListing, DirectTradeProposal


class EscrowServiceTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(
            username="escrow-farmer",
            password="password",
            role=User.Role.FARMER,
            is_active=True,
            is_verified=True,
        )
        self.buyer = User.objects.create_user(
            username="escrow-buyer",
            password="password",
            role=User.Role.BUYER,
            is_active=True,
            is_verified=True,
        )
        self.listing = MarketplaceListing.objects.create(
            listed_by=self.farmer,
            wing="PRODUCE",
            category="Vegetables",
            title="Tomato",
            price=Decimal("50.00"),
            unit_of_measure="kg",
            available_stock=100,
            min_order_quantity=1,
            description="Fresh tomato",
            status="ACTIVE",
        )

    def test_create_payment_transaction(self):
        txn = EscrowService.create_payment_transaction(
            purchaser=self.buyer,
            listing=self.listing,
            amount=Decimal("120.00"),
        )
        self.assertEqual(txn.payment_status, EscrowService.COMPLETED)
        self.assertEqual(txn.amount_paid, Decimal("120.00"))
        self.assertTrue(txn.security_token)

    def test_completed_payment_cannot_move_back(self):
        txn = EscrowService.create_payment_transaction(
            purchaser=self.buyer,
            listing=self.listing,
            amount=Decimal("120.00"),
        )
        with self.assertRaises(ValueError):
            EscrowService.mark_payment_status(
                user=self.buyer,
                transaction_id=txn.pk,
                status=EscrowService.PENDING,
            )

    def test_trade_token_requires_accepted_proposal(self):
        proposal = DirectTradeProposal.objects.create(
            listing=self.listing,
            farmer=self.farmer,
            buyer=self.buyer,
            message="test",
            status="PENDING",
        )
        with self.assertRaises(ValueError):
            EscrowService.generate_trade_token(
                farmer=self.farmer,
                proposal_id=proposal.pk,
            )
