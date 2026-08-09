"""HTTP integration for the legacy Buyer escrow UI.

Existing templates and route contracts are preserved while business rules are
executed through EscrowService and TradeService. Legacy Django models remain
the physical persistence authority during the migration.
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from backend.apps.accounts.models import User
from backend.apps.escrow.services import EscrowService
from backend.apps.trade.services import TradeService
from backend.core.legacy.models import DirectTradeProposal, EscrowTransaction


def _buyer_only(request) -> bool:
    return (
        request.user.is_authenticated
        and request.user.is_active
        and request.user.role == User.Role.BUYER
    )


@login_required
def buyer_scan_qr(request):
    if not _buyer_only(request):
        return redirect("index")
    return render(request, "buyer_scan_qr.html")


@login_required
def buyer_escrow_list(request):
    if not _buyer_only(request):
        return redirect("index")
    deliveries = DirectTradeProposal.objects.filter(
        buyer=request.user,
        status=EscrowService.ACCEPTED,
    ).select_related("listing", "farmer").order_by("-created_at")
    return render(request, "buyer_escrow_list.html", {"deliveries": deliveries})


@login_required
def buyer_escrow_detail(request, proposal_id):
    if not _buyer_only(request):
        return redirect("index")
    proposal = get_object_or_404(
        DirectTradeProposal.objects.select_related("listing", "farmer"),
        pk=proposal_id,
        buyer=request.user,
    )
    total_amount = proposal.total_amount or Decimal("0.00")
    formatted_specs = {
        key.replace("_", " "): value
        for key, value in (proposal.listing.specifications or {}).items()
    }
    escrow = EscrowTransaction.objects.filter(
        purchaser=request.user,
        item_purchased=proposal.listing,
        security_token=proposal.security_token,
    ).order_by("-created_at").first()
    return render(
        request,
        "buyer_escrow_detail.html",
        {
            "proposal": proposal,
            "listing": proposal.listing,
            "total_amount": total_amount,
            "formatted_specs": formatted_specs,
            "escrow": escrow,
        },
    )


@login_required
def buyer_escrow_checkout(request, proposal_id):
    if not _buyer_only(request):
        return redirect("index")

    proposal = get_object_or_404(
        DirectTradeProposal.objects.select_related("listing", "farmer"),
        pk=proposal_id,
        buyer=request.user,
    )
    url_token = request.GET.get("token", "")
    if not proposal.security_token or proposal.security_token != url_token:
        messages.error(request, "SECURITY ALERT: Invalid or expired QR Token. Payment blocked.")
        return redirect("buyer_dashboard")

    if proposal.is_paid or proposal.status == TradeService.COMPLETED:
        messages.warning(request, "This contract has already been paid and completed.")
        return redirect("buyer_proposals")

    total_amount = proposal.total_amount
    if not total_amount or total_amount <= 0:
        messages.error(request, "This proposal does not contain a valid negotiated amount.")
        return redirect("buyer_proposals")

    return render(
        request,
        "buyer_escrow_checkout.html",
        {"proposal": proposal, "listing": proposal.listing, "total_amount": total_amount},
    )


@login_required
@transaction.atomic
def fund_escrow(request, proposal_id):
    if not _buyer_only(request):
        return redirect("index")
    if request.method != "POST":
        return redirect("buyer_escrow_detail", proposal_id=proposal_id)

    try:
        escrow = EscrowService.fund_proposal(
            buyer=request.user,
            proposal_id=proposal_id,
        )
        messages.success(
            request,
            f"₹{escrow.amount_paid} successfully locked in Escrow. The farmer has been notified to dispatch.",
        )
        if escrow.vendor and escrow.vendor.email:
            send_mail(
                f"Escrow Funded: {escrow.item_purchased.title}",
                f"₹{escrow.amount_paid} has been locked in Kultiva escrow for {escrow.item_purchased.title}.",
                "admin@kultiva.com",
                [escrow.vendor.email],
                fail_silently=True,
            )
    except (ValueError, DirectTradeProposal.DoesNotExist) as exc:
        messages.error(request, f"Escrow funding failed: {exc}")
    return redirect("buyer_escrow_list")


@login_required
@transaction.atomic
def process_payment(request, proposal_id):
    """Complete the legacy payment button through the extracted lifecycle."""
    if not _buyer_only(request):
        return redirect("index")
    if request.method != "POST":
        return redirect("buyer_escrow_detail", proposal_id=proposal_id)

    try:
        proposal = get_object_or_404(
            DirectTradeProposal.objects.select_related("listing", "farmer"),
            pk=proposal_id,
            buyer=request.user,
        )
        escrow = EscrowTransaction.objects.filter(
            purchaser=request.user,
            item_purchased=proposal.listing,
            security_token=proposal.security_token,
            payment_status=EscrowService.ESCROW_LOCKED,
        ).order_by("-created_at").first()
        if escrow is None:
            raise ValueError("No locked escrow transaction exists for this proposal.")

        EscrowService.release_funds(user=request.user, transaction_id=escrow.transaction_id)
        EscrowService.mark_proposal_paid(
            buyer=request.user,
            proposal_id=proposal.pk,
            transaction_id=escrow.transaction_id,
        )
        TradeService.complete_trade(user=request.user, proposal_id=proposal.pk)

        listing = proposal.listing
        listing.available_stock = 0
        listing.status = "OUT_OF_STOCK"
        listing.save(update_fields=["available_stock", "status"])

        messages.success(
            request,
            f"Payment of ₹{escrow.amount_paid} successful! The crop ownership has been transferred.",
        )
        receipt = (
            f"Trade completed successfully for {listing.title}. "
            f"Amount released: ₹{escrow.amount_paid}."
        )
        if request.user.email:
            send_mail(
                f"Receipt: {listing.title}", receipt, "admin@kultiva.com",
                [request.user.email], fail_silently=True,
            )
        if listing.listed_by and listing.listed_by.email:
            send_mail(
                f"Funds Released: {listing.title}", receipt, "admin@kultiva.com",
                [listing.listed_by.email], fail_silently=True,
            )
    except (ValueError, DirectTradeProposal.DoesNotExist) as exc:
        messages.error(request, f"Payment failed: {exc}")

    return redirect("buyer_proposals")


@login_required
def request_refund(request, proposal_id):
    """Preserve the legacy dispute workflow; admin remains refund authority."""
    if not _buyer_only(request):
        return redirect("index")
    proposal = get_object_or_404(DirectTradeProposal, pk=proposal_id, buyer=request.user)
    if request.method == "POST":
        escrow = EscrowTransaction.objects.filter(
            purchaser=request.user,
            item_purchased=proposal.listing,
            payment_status=EscrowService.ESCROW_LOCKED,
        ).order_by("-created_at").first()
        reason = request.POST.get("reason", "Not specified")
        description = request.POST.get("description", "").strip()
        transaction_id = escrow.transaction_id if escrow else "N/A"
        amount = escrow.amount_paid if escrow else "Unknown"
        body = (
            "Escrow dispute/refund request\n\n"
            f"Transaction: {transaction_id}\nAmount: ₹{amount}\n"
            f"Contract: KUL-{proposal.pk}\nBuyer: {request.user.username}\n"
            f"Farmer: {proposal.farmer.username}\nReason: {reason}\nDetails: {description}"
        )
        send_mail(
            f"DISPUTE ALERT: Contract KUL-{proposal.pk}", body,
            "admin@kultiva.com", ["admin@kultiva.com"], fail_silently=True,
        )
        messages.info(
            request,
            "Your refund request has been escalated to the Kultiva Admin team for verification.",
        )
    return redirect("buyer_escrow_detail", proposal_id=proposal.pk)


@login_required
def buyer_purchase_history(request):
    if not _buyer_only(request):
        return redirect("index")
    transactions = EscrowTransaction.objects.filter(
        purchaser=request.user,
    ).select_related("item_purchased", "vendor").order_by("-created_at")
    locked = transactions.filter(payment_status=EscrowService.ESCROW_LOCKED)
    completed = transactions.filter(payment_status=EscrowService.COMPLETED)
    refunded = transactions.filter(payment_status=EscrowService.REFUNDED)
    return render(
        request,
        "buyer_purchase_history.html",
        {
            "locked_funds": locked,
            "completed_funds": completed,
            "refunded_funds": refunded,
            "total_locked": locked.aggregate(Sum("amount_paid"))["amount_paid__sum"] or Decimal("0.00"),
            "total_completed": completed.aggregate(Sum("amount_paid"))["amount_paid__sum"] or Decimal("0.00"),
        },
    )


@login_required
def buyer_invoice_detail(request, transaction_id):
    if not _buyer_only(request):
        return redirect("index")
    transaction_record = get_object_or_404(
        EscrowTransaction.objects.select_related("item_purchased", "vendor"),
        transaction_id=transaction_id,
        purchaser=request.user,
    )
    listing = transaction_record.item_purchased
    formatted_specs = {
        key.replace("_", " "): value
        for key, value in (listing.specifications or {}).items()
    }
    return render(
        request,
        "buyer_invoice_detail.html",
        {
            "transaction": transaction_record,
            "txn": transaction_record,
            "listing": listing,
            "formatted_specs": formatted_specs,
        },
    )


__all__ = [
    "buyer_scan_qr", "buyer_escrow_list", "buyer_escrow_detail",
    "buyer_escrow_checkout", "fund_escrow", "process_payment",
    "request_refund", "buyer_purchase_history", "buyer_invoice_detail",
]
