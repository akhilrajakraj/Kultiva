"""Admin HTTP boundary for extracted administrative workflows.

Read-heavy legacy admin pages remain available during migration. State-changing
operations delegate to AdminService so authorization and transitions have one
business boundary while existing URLs and redirects remain stable.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from backend.apps.admin_portal.services import AdminService
from backend.core.legacy import views as legacy_views


# Preserve every legacy read/template endpoint while the admin domain is
# extracted incrementally. The explicit mutations below are the new boundary.
for _name in dir(legacy_views):
    if not _name.startswith("_"):
        globals().setdefault(_name, getattr(legacy_views, _name))


def _admin(request):
    user = request.user
    if not user.is_authenticated:
        return None
    if user.role != user.Role.ADMIN and not user.is_superuser:
        return None
    return user


@login_required
def approve_user(request, user_id: int):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        AdminService.approve_user(admin=admin, user_id=user_id)
        messages.success(request, "User approved successfully.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("admin_dashboard")


@login_required
def farmer_action(request):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        user_id = int(request.POST.get("user_id"))
        action = request.POST.get("action", "").upper()
        if action in {"APPROVE", "VERIFY", "ACCEPT"}:
            AdminService.approve_user(admin=admin, user_id=user_id)
        elif action in {"REJECT", "DECLINE"}:
            AdminService.reject_user(admin=admin, user_id=user_id)
        elif action in {"SUSPEND", "BLOCK"}:
            AdminService.suspend_user(admin=admin, user_id=user_id)
        else:
            raise ValueError("Unsupported farmer action.")
        messages.success(request, "Farmer action completed successfully.")
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
    return redirect("manage_farmers")


@login_required
def buyer_action(request):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        user_id = int(request.POST.get("user_id"))
        action = request.POST.get("action", "").upper()
        if action in {"APPROVE", "VERIFY", "ACCEPT"}:
            AdminService.approve_user(admin=admin, user_id=user_id)
        elif action in {"REJECT", "DECLINE"}:
            AdminService.reject_user(admin=admin, user_id=user_id)
        elif action in {"SUSPEND", "BLOCK"}:
            AdminService.suspend_user(admin=admin, user_id=user_id)
        else:
            raise ValueError("Unsupported buyer action.")
        messages.success(request, "Buyer action completed successfully.")
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
    return redirect("manage_buyers")


@login_required
def seller_action(request):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        user_id = int(request.POST.get("user_id"))
        action = request.POST.get("action", "").upper()
        if action in {"APPROVE", "VERIFY", "ACCEPT"}:
            AdminService.approve_user(admin=admin, user_id=user_id)
        elif action in {"REJECT", "DECLINE"}:
            AdminService.reject_user(admin=admin, user_id=user_id)
        elif action in {"SUSPEND", "BLOCK"}:
            AdminService.suspend_user(admin=admin, user_id=user_id)
        else:
            raise ValueError("Unsupported seller action.")
        messages.success(request, "Seller action completed successfully.")
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
    return redirect("manage_sellers")


@login_required
def process_b2b_refund(request, transaction_id: str):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        AdminService.refund_escrow(admin=admin, transaction_id=transaction_id)
        messages.success(request, "B2B escrow refund processed successfully.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("manage_b2b_refunds")


@login_required
def process_b2c_refund(request, order_id: str):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        AdminService.refund_input_order(admin=admin, order_id=order_id)
        messages.success(request, "B2C order refund processed successfully.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("manage_b2c_refunds")


@login_required
def takedown_product(request, product_id: int):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        AdminService.moderate_listing(admin=admin, listing_id=product_id, action="BAN")
        messages.success(request, "Product has been taken down.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("manage_farmer_products")


@login_required
def update_soil_report(request):
    admin = _admin(request)
    if admin is None:
        messages.error(request, "Administrator privileges are required.")
        return redirect("index")
    try:
        report_id = int(request.POST.get("report_id"))
        status = request.POST.get("status", "PENDING").upper()
        values = {}
        for key in ("nitrogen", "phosphorus", "potassium", "ph"):
            raw = request.POST.get(key)
            if raw not in (None, ""):
                values[key] = float(raw)
        AdminService.update_soil_report(admin=admin, report_id=report_id, status=status, **values)
        messages.success(request, "Soil report updated successfully.")
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))
    return redirect("manage_soil_reports")


__all__ = [name for name in globals() if not name.startswith("_")]
