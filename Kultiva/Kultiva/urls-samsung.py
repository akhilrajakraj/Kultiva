"""Kultiva URL Configuration"""
from django.contrib import admin
from django.urls import path
from . import views
 # from django.conf.urls import url
 # from django.conf import settings
 # from django.conf.urls.static import static

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 1. Public Pages
    path('', views.first, name='first'),
    path('index', views.index, name='index'),
    path('about/', views.about, name='about'), 
    
    # --- DECOUPLED API ENDPOINTS ---
    path('api/pincode/<str:pincode>/', views.pincode_lookup_api, name='pincode_lookup_api'),

    # 2. Authentication (Login/Logout)
    path('login', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    
    # --- PASSWORD RECOVERY ROUTES ---
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('set-new-password/', views.set_new_password, name='set_new_password'), 

    # 3. Registration
    # This URL handles the links like "Register as Farmer" from the login page
    path('register/<str:role_type>/', views.register, name='register_role'),
    
    # This URL handles the actual form submission when you click "Submit"
    path('farmer', views.farmer, name='farmer'),
    path('addfarmer', views.addfarmer, name='addfarmer'),
    path('addbuyer', views.addbuyer, name='addbuyer'),
    path('addseller', views.addseller, name='addseller'),
    
    # Terms and Conditions Page
    path('terms/seller/', views.seller_terms, name='seller_terms'),
    path('terms/farmer/', views.farmer_terms, name='farmer_terms'),
    path('terms/buyer/', views.buyer_terms, name='buyer_terms'),
    
    path('check-email/', views.check_email_availability, name='check_email_availability'),
    path('check-aadhar/', views.check_aadhar_availability, name='check_aadhar_availability'),
    path('check-gst/', views.check_gst_availability, name='check_gst_availability'),
    path('check-shopname/', views.check_shopname_availability, name='check_shopname_availability'),
    path('check-license/', views.check_license_availability, name='check_license_availability'),
    path('check-login-email/', views.check_login_email, name='check_login_email'),
    path('api/check-aadhar/', views.check_aadhar_availability, name='check_aadhar_availability'),
    # (And if you write a check_apeda_availability view, route it here too!)
    path('api/check-apeda/', views.check_apeda_availability, name='check_apeda_availability'),
   
    # 4. Dashboards
    path('farmer/home', views.farmer_home, name='farmer_home'),
    path('buyer/dashboard', views.buyer_dashboard, name='buyer_dashboard'),
    path('seller/dashboard', views.seller_dashboard, name='seller_dashboard'),
    
    # path('dashboard/add-listing/', views.add_listing, name='add_listing'),
    
    # Seller Stock Management
    path('seller/add-item/', views.add_seller_listing, name='add_seller_listing'),
    path('seller/manage-stock/', views.manage_stock, name='manage_stock'),
    path('seller/remove-listing/', views.remove_listing, name='remove_listing'),
    path('seller/edit-listing/<int:listing_id>/', views.edit_listing, name='edit_listing'),
    path('seller/profile/', views.seller_profile_view, name='seller_profile'),
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('seller/reports/', views.seller_reports, name='seller_reports'),
    path('seller/orders/export-csv/', views.export_seller_orders_csv, name='export_seller_orders_csv'),
    path('seller/reports/receipt/<str:order_id>/', views.seller_receipt_detail, name='seller_receipt_detail'),
    path('seller/orders/update/<str:order_id>/', views.update_order_status, name='update_order_status'),
    path('seller/orders/<str:order_id>/', views.seller_order_detail, name='seller_order_detail'),
    path('seller/feedback/', views.seller_feedback, name='seller_feedback'),
    
    
    path('farmer/profile/', views.farmer_profile_view, name='farmer_profile'),
    path('farmer/submit-soil-report/', views.submit_manual_soil, name='submit_manual_soil'),
    path('farmer/add-listing/', views.add_farmer_listing, name='add_farmer_listing'),
    path('farmer/my-crops/', views.farmer_manage_crops, name='farmer_manage_crops'),
    path('farmer/edit-listing/<int:listing_id>/', views.edit_farmer_listing, name='edit_farmer_listing'),
    path('farmer/delete-listing/<int:listing_id>/', views.delete_farmer_listing, name='delete_farmer_listing'),
    path('farmer/send-proposal/', views.send_trade_proposal, name='send_trade_proposal'),
    path('farmer/trade-contracts/', views.farmer_proposals, name='farmer_proposals'),
    path('farmer/contract/<int:proposal_id>/', views.farmer_proposal_detail, name='farmer_proposal_detail'),
    path('farmer/generate-qr/<int:proposal_id>/', views.generate_trade_qr, name='generate_trade_qr'),
    path('farmer/proposal/<int:proposal_id>/respond/', views.farmer_respond_proposal, name='farmer_respond_proposal'),
    path('farmer/input-market/', views.farmer_input_market, name='farmer_input_market'),
    path('farmer/input-market/product/<int:listing_id>/', views.farmer_input_detail, name='farmer_input_detail'),
    path('farmer/checkout/<int:listing_id>/', views.farmer_checkout, name='farmer_checkout'),
    path('farmer/process-order/<int:listing_id>/', views.process_input_order, name='process_input_order'),
    path('farmer/payment-gateway/<int:listing_id>/', views.dummy_payment_gateway, name='dummy_payment_gateway'),
    path('farmer/my-orders/', views.farmer_orders, name='farmer_orders'),
    path('farmer/invoice/<str:order_id>/', views.farmer_invoice_detail, name='farmer_invoice_detail'),
    path('farmer/orders/<str:order_id>/', views.farmer_order_details, name='farmer_order_details'),
    # --- FARMER'S NETWORK (Discovering Verified Input Sellers) ---
    path('farmer/network/sellers/', views.farmer_seller_list, name='farmer_seller_list'),
    path('farmer/network/seller/<int:seller_id>/', views.farmer_view_seller_profile, name='farmer_view_seller_profile'),
    # --- FARMER: FEEDBACK & REPLIES ---
    path('farmer/feedbacks/', views.farmer_feedback_view, name='farmer_feedback_view'),
    path('farmer/reply-feedback/', views.farmer_reply_feedback, name='farmer_reply_feedback'),
    
    
    path('buyer/marketplace/', views.buyer_marketplace, name='buyer_marketplace'),
    path('buyer/marketplace/product/<int:listing_id>/', views.buyer_product_detail, name='buyer_product_detail'),
    path('buyer/marketplace/proposal/<int:listing_id>/', views.submit_buyer_proposal, name='submit_buyer_proposal'),
    path('buyer/my-proposals/', views.buyer_proposals, name='buyer_proposals'),
    path('buyer/proposal/<int:proposal_id>/', views.buyer_proposal_detail, name='buyer_proposal_detail'),
    path('buyer/proposal/<int:proposal_id>/respond/', views.respond_to_proposal, name='respond_to_proposal'),
    path('buyer/scan-qr/', views.buyer_scan_qr, name='buyer_scan_qr'),
    path('buyer/escrow-checkout/<int:proposal_id>/', views.buyer_escrow_checkout, name='buyer_escrow_checkout'),
    path('buyer/process-payment/<int:proposal_id>/', views.process_payment, name='process_payment'),
    path('buyer/escrow-deliveries/', views.buyer_escrow_list, name='buyer_escrow_list'),
    path('buyer/escrow-detail/<int:proposal_id>/', views.buyer_escrow_detail, name='buyer_escrow_detail'),
    path('buyer/fund-escrow/<int:proposal_id>/', views.fund_escrow, name='fund_escrow'),
    path('buyer/request-refund/<int:proposal_id>/', views.request_refund, name='request_refund'),
    path('buyer/negotiations/', views.buyer_negotiations, name='buyer_negotiations'),
    path('buyer/purchase-history/', views.buyer_purchase_history, name='buyer_purchase_history'),
    path('buyer/invoice/<str:transaction_id>/', views.buyer_invoice_detail, name='buyer_invoice_detail'),
    path('buyer/profile/', views.buyer_profile, name='buyer_profile'),
    path('buyer/schedule-pickup/<int:proposal_id>/', views.schedule_pickup, name='schedule_pickup'),
    path('buyer/network/farmers/', views.buyer_farmer_list, name='buyer_farmer_list'),
    # Public profile of a specific farmer showing their active harvests
    path('buyer/network/farmer/<int:farmer_id>/', views.buyer_view_farmer_profile, name='buyer_view_farmer_profile'),
    
    # --- TRUST & FEEDBACK ECOSYSTEM ---
    # Secure endpoint to process reviews for any transaction type
    path('network/submit-review/', views.submit_unified_review, name='submit_unified_review'),
    
    
    
    path('custom-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('custom-admin/manage-farmers/', views.manage_farmers, name='manage_farmers'),
    path('approve/<int:user_id>/', views.approve_user, name='approve_user'),
    path('admin/farmer-action/', views.farmer_action, name='farmer_action'),
    path('custom-admin/farmer/<int:user_id>/', views.view_farmer_profile, name='view_farmer_profile'),
    path('custom-admin/send-email/', views.send_farmer_email, name='send_farmer_email'),
    path('custom-admin/manage-buyers/', views.manage_buyers, name='manage_buyers'),
    path('admin/buyer-action/', views.buyer_action, name='buyer_action'),
    path('custom-admin/buyer/<int:user_id>/', views.view_buyer_profile, name='view_buyer_profile'),
    path('custom-admin/send-buyer-email/', views.send_buyer_email, name='send_buyer_email'),
    path('custom-admin/manage-sellers/', views.manage_sellers, name='manage_sellers'),
    path('admin/seller-action/', views.seller_action, name='seller_action'),
    path('custom-admin/seller/<int:user_id>/', views.view_seller_profile, name='view_seller_profile'),
    path('custom-admin/send-seller-email/', views.send_seller_email, name='send_seller_email'),
    # --- ADMIN: ESCROW & REFUND RESOLUTION CENTER ---
    
    # 1. B2B Escrow (Corporate Buyers cancelling Harvests)
    path('custom-admin/refunds/b2b/', views.manage_b2b_refunds, name='manage_b2b_refunds'),
    path('custom-admin/refunds/b2b/case/<str:transaction_id>/', views.admin_b2b_refund_detail, name='admin_b2b_refund_detail'),
    path('custom-admin/refunds/b2b/process/<str:transaction_id>/', views.process_b2b_refund, name='process_b2b_refund'),
    
    # 2. B2C Orders (Farmers cancelling Seeds/Tools)
    path('custom-admin/refunds/b2c/', views.manage_b2c_refunds, name='manage_b2c_refunds'),
    path('custom-admin/refunds/b2c/case/<str:order_id>/', views.admin_b2c_refund_detail, name='admin_b2c_refund_detail'),
    path('custom-admin/refunds/b2c/process/<str:order_id>/', views.process_b2c_refund, name='process_b2c_refund'),
    # =========================================================
    # --- ADMIN: GLOBAL MARKETPLACE MODERATION ---
    # =========================================================
    
    # 1. Product Directories (The Lists)
    path('custom-admin/products/farmer/', views.manage_farmer_products, name='manage_farmer_products'),
    path('custom-admin/products/seller/', views.manage_seller_products, name='manage_seller_products'),
    
    # 2. Dedicated Product Investigation Dashboard
    path('custom-admin/products/detail/<int:product_id>/', views.admin_product_detail, name='admin_product_detail'),
    
    # 3. The Universal Takedown Action (Executes delete & sends email)
    path('custom-admin/products/takedown/<int:product_id>/', views.takedown_product, name='takedown_product'),
    
    # =========================================================
    # --- ADMIN: GLOBAL ORDER LEDGERS ---
    # =========================================================
    
    # 1. B2C Orders (Seeds/Tools)
    path('custom-admin/orders/seller/', views.manage_seller_orders, name='manage_seller_orders'),
    path('custom-admin/orders/seller/<str:order_id>/', views.admin_seller_order_detail, name='admin_seller_order_detail'),
    
    # 2. B2B Orders (Corporate Harvests)
    path('custom-admin/orders/buyer/', views.manage_buyer_orders, name='manage_buyer_orders'),
    path('custom-admin/orders/buyer/<int:proposal_id>/', views.admin_buyer_order_detail, name='admin_buyer_order_detail'),
    
    # =========================================================
    # --- ADMIN: ENTERPRISE ANALYTICS & REPORTS ---
    # =========================================================
    
    # 1. Farmer Analytics (B2B Harvests, Demographics & Growth)
    path('custom-admin/reports/farmer/', views.admin_farmer_report, name='admin_farmer_report'),
    
    # 2. Seller Analytics (B2C Inputs, Tools & Seed Sales)
    path('custom-admin/reports/seller/', views.admin_seller_report, name='admin_seller_report'),
    
    # 3. Buyer Analytics (Corporate Trade Volume & Escrow Stats)
    path('custom-admin/reports/buyer/', views.admin_buyer_report, name='admin_buyer_report'),
    
    # 5. Admin
    path('admin/', admin.site.urls),
    path('custom-admin/manage-soil-reports/', views.manage_soil_reports, name='manage_soil_reports'),
    path('custom-admin/update-soil-report/', views.update_soil_report, name='update_soil_report'),
    # 4. Platform Feedback Management
    path('custom-admin/feedbacks/', views.admin_manage_feedbacks, name='admin_manage_feedbacks'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)