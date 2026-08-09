"""URL configuration for the restructured Kultiva backend."""
from pathlib import Path
import sys

from django.urls import path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Kultiva.urls import urlpatterns as legacy_urlpatterns  # noqa: E402
from backend.apps.farmers import views as farmer_views  # noqa: E402
from backend.apps.sellers import views as seller_views  # noqa: E402

# Keep every legacy route available except routes that have a verified
# replacement in an extracted domain. This prevents duplicate route names
# from shadowing the new implementation.
_FARMER_ROUTE_NAMES = {
    "farmer_profile", "add_farmer_listing", "farmer_manage_crops",
    "edit_farmer_listing", "delete_farmer_listing", "submit_manual_soil",
    "send_trade_proposal", "farmer_proposals", "farmer_proposal_detail",
    "farmer_respond_proposal", "generate_trade_qr", "farmer_input_market",
    "farmer_input_detail", "farmer_checkout", "process_input_order",
    "dummy_payment_gateway", "farmer_orders", "farmer_invoice_detail",
    "farmer_order_details",
}

_SELLER_ROUTE_NAMES = {
    "seller_dashboard", "add_seller_listing", "manage_stock", "remove_listing",
    "edit_listing", "seller_profile", "seller_orders", "seller_reports",
    "export_seller_orders_csv", "seller_receipt_detail", "update_order_status",
    "seller_order_detail",
}

_EXTRACTED_ROUTE_NAMES = _FARMER_ROUTE_NAMES | _SELLER_ROUTE_NAMES

urlpatterns = [
    route for route in legacy_urlpatterns
    if getattr(route, "name", None) not in _EXTRACTED_ROUTE_NAMES
]

urlpatterns += [
    # Farmer domain
    path("farmer/profile/", farmer_views.profile, name="farmer_profile"),
    path("farmer/add-listing/", farmer_views.add_listing, name="add_farmer_listing"),
    path("farmer/my-crops/", farmer_views.manage_crops, name="farmer_manage_crops"),
    path("farmer/edit-listing/", farmer_views.edit_listing, name="edit_farmer_listing"),
    path("farmer/delete-listing/<int:listing_id>/", farmer_views.delete_listing, name="delete_farmer_listing"),
    path("farmer/submit-soil-report/", farmer_views.submit_soil_report, name="submit_manual_soil"),
    path("farmer/send-proposal/", farmer_views.send_proposal, name="send_trade_proposal"),
    path("farmer/trade-contracts/", farmer_views.proposals, name="farmer_proposals"),
    path("farmer/contract/<int:proposal_id>/", farmer_views.proposal_detail, name="farmer_proposal_detail"),
    path("farmer/proposal/<int:proposal_id>/respond/", farmer_views.respond_proposal, name="farmer_respond_proposal"),
    path("farmer/generate-qr/<int:proposal_id>/", farmer_views.generate_trade_qr, name="generate_trade_qr"),
    path("farmer/input-market/", farmer_views.input_market, name="farmer_input_market"),
    path("farmer/input-market/product/<int:listing_id>/", farmer_views.input_detail, name="farmer_input_detail"),
    path("farmer/checkout/<int:listing_id>/", farmer_views.checkout, name="farmer_checkout"),
    path("farmer/process-order/<int:listing_id>/", farmer_views.process_order, name="process_input_order"),
    path("farmer/payment-gateway/<int:listing_id>/", farmer_views.payment_gateway, name="dummy_payment_gateway"),
    path("farmer/my-orders/", farmer_views.orders, name="farmer_orders"),
    path("farmer/invoice/<str:order_id>/", farmer_views.invoice_detail, name="farmer_invoice_detail"),
    path("farmer/orders/<str:order_id>/", farmer_views.order_detail, name="farmer_order_details"),

    # Seller domain
    path("seller/dashboard", seller_views.seller_dashboard, name="seller_dashboard"),
    path("seller/add-item/", seller_views.add_seller_listing, name="add_seller_listing"),
    path("seller/manage-stock/", seller_views.manage_stock, name="manage_stock"),
    path("seller/remove-listing/", seller_views.remove_listing, name="remove_listing"),
    path("seller/edit-listing/<int:listing_id>/", seller_views.edit_listing, name="edit_listing"),
    path("seller/profile/", seller_views.seller_profile_view, name="seller_profile"),
    path("seller/orders/", seller_views.seller_orders, name="seller_orders"),
    path("seller/reports/", seller_views.seller_reports, name="seller_reports"),
    path("seller/orders/export-csv/", seller_views.export_seller_orders_csv, name="export_seller_orders_csv"),
    path("seller/reports/receipt/<str:order_id>/", seller_views.seller_receipt_detail, name="seller_receipt_detail"),
    path("seller/orders/update/<str:order_id>/", seller_views.update_order_status, name="update_order_status"),
    path("seller/orders/<str:order_id>/", seller_views.seller_order_detail, name="seller_order_detail"),
]
