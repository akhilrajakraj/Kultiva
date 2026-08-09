import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.test import TestCase

from backend.apps.accounts.models import User
from backend.apps.escrow.models import DirectTradeProposal, EscrowTransaction, MarketplaceListing
from backend.apps.escrow.services import EscrowService


class EscrowServiceTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(
            username="farmer-escrow",
            email="farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_active=True,
        )
        self.buyer = User.objects.create_user(
            username="buyer-escrow",
            email="buyer@example.com",
            password="test-password",
            role=User.Role.BUYER,
            is_active=True,
        )
        self.other_buyer = User.objects.create_user(
            username="other-buyer-escrow",
            email="other@example.com",
            password="test-password",
            role=User.Role.BUYER,
            is_active=True,
        )
        self.listing = MarketplaceListing.objects.create(
            listed_by=self.farmer,
            wing="PRODUCE",
            category="GRAINS",
            title="Premium Rice",
            description="B2B rice supply",
            price=Decimal("80.00"),
            unit_of_measure="kg",
            available_stock=1000,
            min_order_quantity=10,
        )
        self.proposal = DirectTradeProposal.objects.create(
            listing=self.listing,
            farmer=self.farmer,
            buyer=self.buyer,
            status="ACCEPTED",
            requested_quantity=100,
            proposed_price=Decimal("75.00"),
            total_amount=Decimal("7500.00"),
        )

    def test_fund_proposal_creates_locked_escrow_with_negotiated_amount(self):
        escrow = EscrowService.fund_proposal(
            buyer=self.buyer,
            proposal_id=self.proposal.pk,
        )

        self.assertEqual(escrow.payment_status, EscrowService.ESCROW_LOCKED)
        self.assertEqual(escrow.amount_paid, Decimal("7500.00"))
        self.assertEqual(escrow.purchaser_id, self.buyer.pk)
        self.assertEqual(escrow.vendor_id, self.farmer.pk)
        self.assertEqual(escrow.item_purchased_id, self.listing.pk)
        self.proposal.refresh_from_db()
        self.assertTrue(self.proposal.security_token)
        self.assertEqual(escrow.security_token, self.proposal.security_token)

    def test_fund_proposal_is_idempotent(self):
        first = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)
        second = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            EscrowTransaction.objects.filter(
                purchaser=self.buyer,
                item_purchased=self.listing,
            ).count(),
            1,
        )

    def test_only_buyer_can_fund_proposal(self):
        with self.assertRaisesMessage(ValueError, "Only buyers can fund a trade."):
            EscrowService.fund_proposal(buyer=self.farmer, proposal_id=self.proposal.pk)

    def test_only_accepted_proposal_can_be_funded(self):
        self.proposal.status = "PENDING"
        self.proposal.save(update_fields=["status"])

        with self.assertRaisesMessage(ValueError, "Only accepted proposals can be funded."):
            EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)

    def test_other_buyer_cannot_fund_someone_elses_proposal(self):
        with self.assertRaises(DirectTradeProposal.DoesNotExist):
            EscrowService.fund_proposal(
                buyer=self.other_buyer,
                proposal_id=self.proposal.pk,
            )

    def test_release_funds_transitions_locked_to_completed(self):
        escrow = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)

        released = EscrowService.release_funds(
            user=self.buyer,
            transaction_id=escrow.transaction_id,
        )

        self.assertEqual(released.payment_status, EscrowService.COMPLETED)

    def test_release_funds_rejects_already_completed_transaction(self):
        escrow = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)
        EscrowService.release_funds(user=self.buyer, transaction_id=escrow.transaction_id)

        with self.assertRaisesMessage(ValueError, "Only locked escrow funds can be released."):
            EscrowService.release_funds(user=self.buyer, transaction_id=escrow.transaction_id)

    def test_refund_funds_transitions_locked_to_refunded(self):
        escrow = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)

        refunded = EscrowService.refund_funds(
            user=self.buyer,
            transaction_id=escrow.transaction_id,
        )

        self.assertEqual(refunded.payment_status, EscrowService.REFUNDED)

    def test_refund_cannot_reverse_completed_transaction(self):
        escrow = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)
        EscrowService.release_funds(user=self.buyer, transaction_id=escrow.transaction_id)

        with self.assertRaisesMessage(ValueError, "Only locked escrow funds can be refunded."):
            EscrowService.refund_funds(user=self.buyer, transaction_id=escrow.transaction_id)

    def test_mark_proposal_paid_requires_completed_matching_escrow(self):
        escrow = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)

        with self.assertRaisesMessage(ValueError, "Proposal cannot be marked paid before escrow is completed."):
            EscrowService.mark_proposal_paid(
                buyer=self.buyer,
                proposal_id=self.proposal.pk,
                transaction_id=escrow.transaction_id,
            )

        EscrowService.release_funds(user=self.buyer, transaction_id=escrow.transaction_id)
        proposal = EscrowService.mark_proposal_paid(
            buyer=self.buyer,
            proposal_id=self.proposal.pk,
            transaction_id=escrow.transaction_id,
        )

        self.assertTrue(proposal.is_paid)

    def test_mark_proposal_paid_rejects_amount_mismatch(self):
        escrow = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)
        EscrowService.release_funds(user=self.buyer, transaction_id=escrow.transaction_id)

        self.proposal.total_amount = Decimal("7600.00")
        self.proposal.save(update_fields=["total_amount"])

        with self.assertRaisesMessage(ValueError, "Escrow amount does not match the negotiated proposal amount."):
            EscrowService.mark_proposal_paid(
                buyer=self.buyer,
                proposal_id=self.proposal.pk,
                transaction_id=escrow.transaction_id,
            )

    def test_transaction_access_is_participant_only(self):
        escrow = EscrowService.fund_proposal(buyer=self.buyer, proposal_id=self.proposal.pk)

        with self.assertRaisesMessage(ValueError, "You do not have access to this escrow transaction."):
            EscrowService.release_funds(
                user=self.other_buyer,
                transaction_id=escrow.transaction_id,
            )
