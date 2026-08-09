"""HTTP adapters for the legacy buyer escrow workflow.

These views preserve the existing URLs, templates, messages, and database
contract while delegating escrow business rules to EscrowService. The legacy
Kultiva views remain available for non-escrow functionality during migration.
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import strip_tags

from backend.apps.escrow.services import EscrowService
from backend.core.legacy.models import DirectTradeProposal, EscrowTransaction


@login_required
def buyer_escrow_checkout(request, proposal_id):
    """Render the existing checkout UI using negotiated proposal terms."""
    if request.user.role != request.user.Role.BUYER:
        return redirect("index")

    proposal = get_object_or_404(
        DirectTradeProposal.objects.select_related("listing", "farmer"),
        pk=proposal_id,
        buyer=request.user,
    )

    token = request.GET.get("token")
    if not token or proposal.security_token != token:
        messages.error(request, "SECURITY ALERT: Invalid or expired QR Token. Payment blocked.")
        return redirect("buyer_dashboard")

    if proposal.is_paid or proposal.status == "COMPLETED":
        messages.warning(request, "This contract has already been paid and completed.")
        return redirect("buyer_proposals")

    if proposal.status != EscrowService.ACCEPTED:
        messages.error(request, "Only accepted trade proposals can enter escrow checkout.")
        return redirect("buyer_proposals")

    total_amount = proposal.total_amount
    if total_amount <= 0:
        messages.error(request, "This proposal has no valid negotiated amount.")
        return redirect("buyer_proposal_detail", proposal_id=proposal.id)

    return render(
        request,
        "buyer_escrow_checkout.html",
        {
            "proposal": proposal,
            "listing": proposal.listing,
            "total_amount": total_amount,
        },
    )


@login_required
def process_payment(request, proposal_id):
    """Preserve the legacy payment endpoint while using the escrow service."""
    if request.method != "POST" or request.user.role != request.user.Role.BUYER:
        return redirect("buyer_proposals")

    try:
        with transaction.atomic():
            proposal = get_object_or_404(
                DirectTradeProposal.objects.select_for_update().select_related("listing", "farmer"),
                pk=proposal_id,
                buyer=request.user,
            )

            if proposal.is_paid:
                messages.error(request, "Payment already processed.")
                return redirect("buyer_proposals")

            if proposal.status != EscrowService.ACCEPTED:
                messages.error(request, "Only accepted proposals can be paid.")
                return redirect("buyer_proposals")

            escrow = EscrowService.fund_proposal(
                buyer=request.user,
                proposal_id=proposal.id,
            )
            escrow = EscrowService.release_funds(
                user=request.user,
                transaction_id=escrow.transaction_id,
            )
            EscrowService.mark_proposal_paid(
                buyer=request.user,
                proposal_id=proposal.id,
                transaction_id=escrow.transaction_id,
            )

            # Preserve the legacy inventory behavior: the completed trade
            # consumes the currently available stock for this listing.
            listing = proposal.listing
            listing.available_stock = 0
            listing.status = "OUT_OF_STOCK"
            listing.save(update_fields=["available_stock", "status"])

            receipt_html = f"""
            <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
                <h2 style="color: #2e7d32;">Trade Completed Successfully</h2>
                <p>The digital handshake for <strong>{listing.title}</strong> is complete.</p>
                <div style="background: #f1f8e9; padding: 15px; border-left: 4px solid #2e7d32;">
                    <h3>Payment Released from Escrow</h3>
                    <p><strong>Amount:</strong> ₹{escrow.amount_paid}</p>
                    <p><strong>Farmer:</strong> {listing.listed_by.username}</p>
                    <p><strong>Buyer:</strong> {request.user.username}</p>
                    <p><strong>Transaction:</strong> {escrow.transaction_id}</p>
                </div>
            </div>
            """
            send_mail(
                f"Receipt: {listing.title}",
                strip_tags(receipt_html),
                "admin@kultiva.com",
                [request.user.email],
                html_message=receipt_html,
                fail_silently=True,
            )
            send_mail(
                f"Funds Released: {listing.title}",
                strip_tags(receipt_html),
                "admin@kultiva.com",
                [listing.listed_by.email],
                html_message=receipt_html,
                fail_silently=True,
            )

            messages.success(
                request,
                f"Payment of ₹{escrow.amount_paid} successful! The crop ownership has been transferred.",
            )
    except ValueError as exc:
        messages.error(request, f"Payment failed: {exc}")
    except Exception as exc:
        messages.error(request, f"Payment failed: {exc}")

    return redirect("buyer_proposals")


@login_required
def buyer_escrow_list(request):
    if request.user.role != request.user.Role.BUYER:
        return redirect("index")

    deliveries = DirectTradeProposal.objects.filter(
        buyer=request.user,
        status=EscrowService.ACCEPTED,
    ).select_related("listing", "farmer").order_by("-created_at")
    return render(request, "buyer_escrow_list.html", {"deliveries": deliveries})


@login_required
def buyer_escrow_detail(request, proposal_id):
    if request.user.role != request.user.Role.BUYER:
        return redirect("index")

    proposal = get_object_or_404(
        DirectTradeProposal.objects.select_related("listing", "farmer"),
        pk=proposal_id,
        buyer=request.user,
    )
    formatted_specs = {
        key.replace("_", " "): value
        for key, value in (proposal.listing.specifications or {}).items()
    }
    return render(
        request,
        "buyer_escrow_detail.html",
        {
            "proposal": proposal,
            "listing": proposal.listing,
            "total_amount": proposal.total_amount,
            "formatted_specs": formatted_specs,
        },
    )


@login_required
def fund_escrow(request, proposal_id):
    """Lock negotiated proposal funds without completing the trade."""
    if request.method != "POST" or request.user.role != request.user.Role.BUYER:
        return redirect("buyer_escrow_list")

    try:
        escrow = EscrowService.fund_proposal(
            buyer=request.user,
            proposal_id=proposal_id,
        )
        proposal = get_object_or_404(
            DirectTradeProposal.objects.select_related("listing", "farmer"),
            pk=proposal_id,
            buyer=request.user,
        )

        farmer_html = f"""
        <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
            <h2 style="color: #2e7d32;">Funds Locked in Escrow!</h2>
            <p>The buyer has successfully deposited <strong>₹{escrow.amount_paid}</strong> into the Kultiva Escrow Vault for <strong>{proposal.listing.title}</strong>.</p>
            <div style="background: #fff8e1; border-left: 4px solid #fbc02d; padding: 15px; margin: 20px 0;">
                <strong>Action Required:</strong> Please dispatch the goods. Funds remain locked until settlement.
            </div>
        </div>
        """
        send_mail(
            f"Escrow Funded: {proposal.listing.title}",
            strip_tags(farmer_html),
            "admin@kultiva.com",
            [proposal.listing.listed_by.email],
            html_message=farmer_html,
            fail_silently=True,
        )
        messages.success(
            request,
            f"₹{escrow.amount_paid} successfully locked in Escrow. The farmer has been notified to dispatch.",
        )
    except ValueError as exc:
        messages.error(request, f"Escrow Funding failed: {exc}")
    except Exception as exc:
        messages.error(request, f"Escrow Funding failed: {exc}")

    return redirect("buyer_escrow_list")


@login_required
def request_refund(request, proposal_id):
    """Preserve the legacy admin-dispute workflow without mutating escrow state."""
    if request.method != "POST" or request.user.role != request.user.Role.BUYER:
        return redirect("buyer_escrow_list")

    proposal = get_object_or_404(
        DirectTradeProposal.objects.select_related("listing", "farmer"),
        pk=proposal_id,
        buyer=request.user,
    )
    reason = request.POST.get("reason", "Not specified")
    description = request.POST.get("description", "").strip()
    escrow_txn = EscrowTransaction.objects.filter(
        purchaser=request.user,
        item_purchased=proposal.listing,
        payment_status=EscrowService.ESCROW_LOCKED,
    ).first()

    if not escrow_txn:
        messages.error(request, "No locked escrow transaction was found for this proposal.")
        return redirect("buyer_escrow_detail", proposal_id=proposal.id)

    admin_html = f"""
    <div style="font-family: Arial; padding: 20px; border: 1px solid #d32f2f; border-radius: 10px;">
        <h2 style="color: #d32f2f;">URGENT: Escrow Dispute / Refund Request</h2>
        <p>A buyer has requested a refund for locked escrow funds. Investigation required.</p>
        <div style="background: #ffebee; padding: 15px; border-left: 4px solid #d32f2f;">
            <p><strong>Transaction ID:</strong> {escrow_txn.transaction_id}</p>
            <p><strong>Amount Locked:</strong> ₹{escrow_txn.amount_paid}</p>
            <p><strong>Contract Ref:</strong> KUL-{proposal.id}</p>
            <p><strong>Buyer:</strong> {request.user.username}</p>
            <p><strong>Vendor:</strong> {proposal.farmer.username}</p>
            <hr>
            <p><strong>Dispute Reason:</strong> {reason}</p>
            <p><strong>Details:</strong> {description}</p>
        </div>
        <p>Please review the case in the Admin Dashboard before changing the escrow state.</p>
    </div>
    """
    send_mail(
        f"DISPUTE ALERT: Contract KUL-{proposal.id}",
        strip_tags(admin_html),
        "admin@kultiva.com",
        ["admin@kultiva.com"],
        html_message=admin_html,
        fail_silently=True,
    )
    messages.info(
        request,
        "Your refund request has been escalated to the Kultiva Admin team. The locked funds were not changed automatically.",
    )
    return redirect("buyer_escrow_detail", proposal_id=proposal.id)


__all__ = [
    "buyer_escrow_checkout",
    "process_payment",
    "buyer_escrow_list",
    "buyer_escrow_detail",
    "fund_escrow",
    "request_refund",
]
