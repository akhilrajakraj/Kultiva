from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.db import transaction
from .models import User, Address, FarmerProfile, BuyerProfile, SellerProfile, MarketplaceListing, ManualSoilReport, DirectTradeProposal, EscrowTransaction, InputOrder, UnifiedReview # Import your new models
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail, EmailMultiAlternatives
from .utils import get_weather, get_soil_for_location, predict_best_crop, IndianAgriGeocoder
from django.utils.html import strip_tags
import uuid, random, qrcode, datetime, calendar
from io import BytesIO
from django.core.files import File
from decimal import Decimal
from django.utils.dateparse import parse_datetime
import csv, time
from django.utils import timezone
from .advisory_db import CROP_ADVISORY_DB
import logging
import json
from datetime import timedelta
from django.utils import timezone
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.db.models import F, FloatField, ExpressionWrapper
from django.conf import settings

def first(request):
    return render(request, 'index.html')
def index(request):
    return render(request, 'index.html')
def about(request):
    """
    Renders the public 'About Us' page detailing the Kultiva project and team.
    """
    return render(request, 'about.html')


def farmer(request):
    return render(request, 'farmerregister.html')

# --- Placeholder Views for Dashboards (So redirects don't fail) ---
# --- FARMER DASHBOARD ---
logger = logging.getLogger(__name__)
@login_required
def farmer_home(request):
    """
    Core Farmer Dashboard View: Compiles micro-climate, localized soil parameters, 
    user overrides, and ML predictions into a unified data context.
    """
    try:
        # 1. Geographic Baseline (Default to Kerala Center)
        lat, lon = 10.8505, 76.2711 
        location_name = "Kerala Region"

        # Try to resolve high-precision coordinates from the user profile
        user_address = request.user.addresses.first()
        if user_address:
            location_name = getattr(user_address, 'district', location_name) or location_name
            if user_address.latitude and user_address.longitude:
                try:
                    lat_val, lon_val = float(user_address.latitude), float(user_address.longitude)
                    if lat_val != 0.0 and lon_val != 0.0:
                        lat, lon = lat_val, lon_val
                except ValueError:
                    logger.warning(f"Invalid coordinate format for user {request.user.id}")

        # 2. Fire Baseline Data Engines
        weather_data = get_weather(lat, lon, location_name) or {}
        soil_data = get_soil_for_location(lat, lon) or {}
        
        # 3. Assess Laboratory Overrides (Manual Reports)
        manual_report = ManualSoilReport.objects.filter(farmer=request.user).first()
        
        if manual_report and manual_report.request_status == 'COMPLETED':
            # Safely inject verified lab inputs, fallback to API data if field was left blank
            soil_data['pH'] = manual_report.ph if manual_report.ph is not None else soil_data.get('pH', 7.0)
            soil_data['N'] = manual_report.n if manual_report.n is not None else soil_data.get('N', 50)
            soil_data['P'] = manual_report.p if manual_report.p is not None else soil_data.get('P', 50)
            soil_data['K'] = manual_report.k if manual_report.k is not None else soil_data.get('K', 50)
            
            soil_data['Advisory'] = "High-precision AI analysis utilizing verified local laboratory test data."
            soil_data['Status'] = "Manual Lab Data Active"
            soil_data['found'] = True

        # 4. Execute Machine Learning Agronomist Pipeline
        ai_recommendation = predict_best_crop(weather_data, soil_data)
        
        predicted_crop = ai_recommendation.get('crop', '') if ai_recommendation.get('success') else ""
        ranked_predictions = ai_recommendation.get('predictions',[])

        # 5. Fetch Ecosystem Integrations (Marketplace & Advisory)
        recommended_products = None
        crop_guide = None

        if predicted_crop:
            # Optimize DB queries utilizing prefetch/select related
            recommended_products = MarketplaceListing.objects.filter(
                Q(title__icontains=predicted_crop) | Q(description__icontains=predicted_crop),
                category='SEEDS',
                status='ACTIVE',
                available_stock__gt=0
            ).select_related('listed_by').order_by('-available_stock')[:4]

            # Deep Advisory DB lookup logic with tuple-failsafe
            crop_key = predicted_crop.strip().title()
            
            try:
                # Failsafe: Handles potential typo in configuration where CROP_ADVISORY_DB is a tuple
                safe_advisory_db = CROP_ADVISORY_DB[0] if isinstance(CROP_ADVISORY_DB, tuple) else CROP_ADVISORY_DB
                crop_guide = safe_advisory_db.get(crop_key)
            except Exception as e:
                logger.error(f"Error accessing CROP_ADVISORY_DB: {e}")
                crop_guide = None

        # 6. Construct Immutable Output Context
        context = {
            'weather': weather_data,
            'soil': soil_data,
            'location': location_name,
            'manual_report': manual_report,
            'ai_result': ai_recommendation, 
            'ranked_predictions': ranked_predictions,
            'predicted_crop': predicted_crop,              
            'recommended_products': recommended_products,  
            'crop_guide': crop_guide,                      
        }
        
        return render(request, 'farmer_home.html', context)

    except Exception as e:
        logger.critical(f"Critical failure in farmer_home view for user {request.user.username}: {str(e)}", exc_info=True)
        # Fallback render to prevent 500 error page if system entirely fails
        return render(request, 'farmer_home.html', {
            'ai_result': {"success": False, "status": "System currently undergoing maintenance."}
        })
        
# --- FARMER PROFILE MANAGEMENT ---
@login_required
def farmer_profile_view(request):
    if request.user.role != User.Role.FARMER:
        return redirect('index')

    address = request.user.addresses.first()
    profile = getattr(request.user, 'farmer_profile', None)

    if request.method == 'POST':
        # 1. Update Allowed User Fields
        new_username = request.POST.get('username')
        if new_username:
            request.user.username = new_username
            request.user.save()

        # 2. Update Allowed Address Fields & GPS
        if address:
            address.village = request.POST.get('village')
            address.district = request.POST.get('district')
            address.state = request.POST.get('state')
            address.pincode = request.POST.get('pincode')
            
            # --- THE SMART GEOSPATIAL ENGINE ---
            provided_lat = request.POST.get('latitude', '').strip()
            provided_lon = request.POST.get('longitude', '').strip()

            # If user leaves them blank or types 0.0, we Auto-Generate them!
            if not provided_lat or not provided_lon or float(provided_lat) == 0.0 or float(provided_lon) == 0.0:
                geo_engine = IndianAgriGeocoder()
                auto_lat, auto_lon = geo_engine.get_coordinates(address.district, address.state)
                address.latitude = auto_lat
                address.longitude = auto_lon
                messages.success(request, f"Profile updated. GPS Coordinates Auto-Generated based on {address.district}.")
            else:
                # If they typed specific numbers, save those.
                try:
                    address.latitude = float(provided_lat)
                    address.longitude = float(provided_lon)
                    messages.success(request, "Profile and manual GPS Coordinates updated successfully!")
                except ValueError:
                    messages.error(request, "Invalid GPS format. Keeping previous coordinates.")
                
            address.save()

        return redirect('farmer_profile')

    # Security: Mask the Aadhar Number for display
    masked_aadhar = "N/A"
    if profile and profile.aadhar_no:
        if len(profile.aadhar_no) >= 4:
            masked_aadhar = "********" + profile.aadhar_no[-4:]
        else:
            masked_aadhar = "****"

    context = {
        'address': address,
        'profile': profile,
        'masked_aadhar': masked_aadhar
    }
    
    return render(request, 'farmer_profile.html', context)

@login_required
def add_farmer_listing(request):
    if request.method == 'POST' and request.user.role == User.Role.FARMER:
        try:
            # 1. Capture Standard Fields
            category = request.POST.get('category')
            title = request.POST.get('title')
            variety = request.POST.get('variety_or_brand')
            price = request.POST.get('price')
            unit = request.POST.get('unit_of_measure')
            stock = request.POST.get('available_stock')
            min_order = request.POST.get('min_order_quantity')
            description = request.POST.get('description')
            grade = request.POST.get('grade')
            harvest_date = request.POST.get('harvest_date')
            is_organic = request.POST.get('is_organic') == 'on'
            image = request.FILES.get('image')

            # 2. Pack Dynamic "Magic Field" Data
            specs = {}
            if request.POST.get('moisture_content'):
                specs['moisture'] = request.POST.get('moisture_content')
            if request.POST.get('shelf_life'):
                specs['shelf_life'] = request.POST.get('shelf_life')
            if request.POST.get('broken_ratio'):
                specs['broken_ratio'] = request.POST.get('broken_ratio')

            # 3. Save to Database
            listing = MarketplaceListing.objects.create(
                listed_by=request.user,
                wing='PRODUCE',
                category=category,
                title=title,
                variety_or_brand=variety,
                price=price,
                unit_of_measure=unit,
                available_stock=stock,
                min_order_quantity=min_order,
                description=description,
                grade=grade,
                harvest_date=harvest_date if harvest_date else None,
                is_organic=is_organic,
                image=image,
                specifications=specs
            )

            # --- 4. SEND BEAUTIFUL HTML EMAILS ---
            
            # Email 1: To the Farmer (Receipt)
            farmer_subject = f"Kultiva: Listing Published - {title}"
            farmer_html = f"""
            <html>
            <body style="font-family: 'Times New Roman', Times, serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                    <div style="background-color: #1b5e20; color: #ffffff; padding: 20px; text-align: center;">
                        <h2 style="margin: 0; color: #fbc02d;">KULTIVA MARKET</h2>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">Listing Successful</p>
                    </div>
                    <div style="padding: 30px; color: #333333;">
                        <h3 style="color: #2e7d32;">Hello {request.user.username},</h3>
                        <p>Your harvest has been successfully listed on the global marketplace. Verified buyers have been notified.</p>
                        <div style="background-color: #f9f9f9; border-left: 4px solid #fbc02d; padding: 15px; margin: 20px 0; border-radius: 5px;">
                            <ul style="list-style-type: none; padding: 0; margin: 0;">
                                <li style="padding-bottom: 8px;"><strong>Item:</strong> {title} ({category})</li>
                                <li style="padding-bottom: 8px;"><strong>Stock:</strong> {stock} {unit}</li>
                                <li style="padding-bottom: 8px;"><strong>Price:</strong> ₹{price} / {unit}</li>
                            </ul>
                        </div>
                        <p>We will notify you via the dashboard when a buyer places a bid.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            send_mail(
                subject=farmer_subject, message=strip_tags(farmer_html),
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'admin@kultiva.com',
                recipient_list=[request.user.email], html_message=farmer_html, fail_silently=True
            )

            # Email 2: To all Verified Buyers (Alert)
            verified_buyers = User.objects.filter(role=User.Role.BUYER, is_verified=True).values_list('email', flat=True)
            if verified_buyers:
                buyer_subject = f"New Supply Alert: {title} available in {request.user.addresses.first().district if request.user.addresses.exists() else 'your region'}"
                buyer_html = f"""
                <html>
                <body style="font-family: 'Times New Roman', Times, serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                        <div style="background-color: #1e293b; color: #ffffff; padding: 20px; text-align: center;">
                            <h2 style="margin: 0; color: #fbc02d;">KULTIVA MARKET ALERT</h2>
                            <p style="margin: 5px 0 0 0; font-size: 14px;">Fresh Inventory Available</p>
                        </div>
                        <div style="padding: 30px; color: #333333;">
                            <p>A verified farmer has just listed new inventory that matches your procurement network.</p>
                            <div style="background-color: #e3f2fd; border-left: 4px solid #0288d1; padding: 15px; margin: 20px 0; border-radius: 5px;">
                                <h3 style="margin-top: 0; color: #0288d1;">{title}</h3>
                                <ul style="list-style-type: none; padding: 0; margin: 0;">
                                    <li style="padding-bottom: 8px;"><strong>Variety:</strong> {variety}</li>
                                    <li style="padding-bottom: 8px;"><strong>Available:</strong> {stock} {unit}</li>
                                    <li style="padding-bottom: 8px;"><strong>Grade:</strong> {grade} {'(Organic)' if is_organic else ''}</li>
                                </ul>
                            </div>
                            <p style="text-align: center; margin-top: 30px;">
                                <a href="#" style="background-color: #1b5e20; color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; font-weight: bold;">View Details on Dashboard</a>
                            </p>
                        </div>
                    </div>
                </body>
                </html>
                """
                # Use the advanced engine for BCC privacy
                from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'admin@kultiva.com'
                msg = EmailMultiAlternatives(
                    subject=buyer_subject,
                    body=strip_tags(buyer_html),
                    from_email=from_email,
                    to=[], # No primary recipient
                    bcc=list(verified_buyers) # Hidden recipients
                )
                msg.attach_alternative(buyer_html, "text/html")
                msg.send(fail_silently=True)

            messages.success(request, "Your harvest has been successfully listed on the marketplace!")
            return redirect('farmer_home')
            
        except Exception as e:
            messages.error(request, f"Error creating listing: {e}")
            return redirect('farmer_home')

    return render(request, 'farmer_add_listing.html')

# --- INVENTORY MANAGEMENT & TRADE PROPOSALS ---
@login_required
def farmer_manage_crops(request):
    if request.user.role != User.Role.FARMER:
        return redirect('index')
        
    # Fetch farmer's active/hidden listings
    my_listings = MarketplaceListing.objects.filter(listed_by=request.user).order_by('-created_at')
    
    # Fetch all verified buyers for the dropdown
    verified_buyers = User.objects.filter(role=User.Role.BUYER, is_verified=True)
    
    return render(request, 'farmer_manage_crops.html', {
        'listings': my_listings,
        'buyers': verified_buyers
    })

@login_required
def edit_farmer_listing(request):
    if request.method == 'POST':
        listing_id = request.POST.get('listing_id')
        new_price = request.POST.get('price')
        new_stock = request.POST.get('stock')
        
        listing = get_object_or_404(MarketplaceListing, id=listing_id, listed_by=request.user)
        listing.price = new_price
        listing.available_stock = new_stock
        listing.save()
        
        # Simple email notification for edit
        send_mail(
            "Kultiva: Listing Updated",
            f"Your listing '{listing.title}' has been updated to ₹{new_price} with {new_stock} stock.",
            'admin@kultiva.com',
            [request.user.email],
            fail_silently=True
        )
        messages.success(request, "Listing updated successfully.")
    return redirect('farmer_manage_crops')

@login_required
def delete_farmer_listing(request, listing_id):
    listing = get_object_or_404(MarketplaceListing, id=listing_id, listed_by=request.user)
    title = listing.title
    listing.delete()
    
    # Simple email notification for deletion
    send_mail(
        "Kultiva: Listing Removed",
        f"Your listing '{title}' has been permanently removed from the marketplace.",
        'admin@kultiva.com',
        [request.user.email],
        fail_silently=True
    )
    messages.warning(request, f"'{title}' has been removed from your inventory.")
    return redirect('farmer_manage_crops')

@login_required
def send_trade_proposal(request):
    if request.method == 'POST':
        listing_id = request.POST.get('listing_id')
        buyer_id = request.POST.get('buyer_id')
        visibility_action = request.POST.get('visibility_action') # Keep or Hide
        message = request.POST.get('message', '')
        
        listing = get_object_or_404(MarketplaceListing, id=listing_id, listed_by=request.user)
        buyer = get_object_or_404(User, user_id=buyer_id, role=User.Role.BUYER)
        
        # 1. Create the 3NF Proposal
        proposal, created = DirectTradeProposal.objects.get_or_create(
            listing=listing,
            farmer=request.user,
            buyer=buyer,
            defaults={'message': message, 'status': 'PENDING'}
        )
        
        if not created:
            messages.error(request, "You already have a pending proposal with this buyer for this item.")
            return redirect('farmer_manage_crops')
            
        # 2. Handle the "Hide from Market" logic
        if visibility_action == 'HIDE':
            listing.status = 'HIDDEN'
            listing.save()
            vis_msg = "It has been hidden from the public market as an exclusive offer."
        else:
            vis_msg = "It remains visible on the public market."

        # 3. Send Email to BUYER
        buyer_html = f"""
        <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
            <h2 style="color: #1b5e20;">Direct Trade Offer Received</h2>
            <p><strong>{request.user.username}</strong> has sent you a direct proposal for their harvest.</p>
            <div style="background: #f9f9f9; padding: 15px; border-left: 4px solid #fbc02d;">
                <h3>{listing.title}</h3>
                <p><strong>Stock:</strong> {listing.available_stock} {listing.unit_of_measure}</p>
                <p><strong>Price:</strong> ₹{listing.price}</p>
                <p><strong>Message:</strong> "{message}"</p>
            </div>
            <p>Please log in to your Buyer Dashboard to accept or reject this offer.</p>
        </div>
        """
        send_mail(
            f"Trade Offer: {listing.title}", strip_tags(buyer_html), 'admin@kultiva.com',
            [buyer.email], html_message=buyer_html, fail_silently=True
        )
        
        # 4. Send Email to FARMER (Receipt)
        farmer_html = f"""
        <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
            <h2 style="color: #1b5e20;">Proposal Sent Successfully</h2>
            <p>Your direct offer for <strong>{listing.title}</strong> has been sent to <strong>{buyer.username}</strong>.</p>
            <p><em>{vis_msg}</em></p>
            <p>You will be notified once the buyer responds.</p>
        </div>
        """
        send_mail(
            f"Proposal Sent: {buyer.username}", strip_tags(farmer_html), 'admin@kultiva.com',
            [request.user.email], html_message=farmer_html, fail_silently=True
        )
        
        messages.success(request, f"Trade proposal successfully sent to {buyer.username}!")
    return redirect('farmer_manage_crops')

@login_required
def submit_manual_soil(request):
    if request.method == 'POST' and request.user.role == User.Role.FARMER:
        try:
            # 1. Capture required fields
            land_area = float(request.POST.get('land_area', 0))
            previous_crop = request.POST.get('previous_crop', '').strip()
            
            # 2. Capture optional NPK/pH values
            ph = request.POST.get('ph')
            n = request.POST.get('n')
            p = request.POST.get('p')
            k = request.POST.get('k')
            
            # Convert empty strings to None
            ph = float(ph) if ph else None
            n = float(n) if n else None
            p = float(p) if p else None
            k = float(k) if k else None

            # 3. Use update_or_create because of the OneToOneField
            # This prevents database crashes if they submit twice
            report, created = ManualSoilReport.objects.update_or_create(
                farmer=request.user,
                defaults={
                    'land_area': land_area,
                    'previous_crop': previous_crop,
                    'ph': ph,
                    'n': n,
                    'p': p,
                    'k': k,
                    'request_status': 'PENDING'
                }
            )

            # 4. Generate the Beautiful HTML Email
            subject = 'Kultiva - Soil Lab Request Submitted Successfully'
            html_message = f"""
            <html>
            <body style="font-family: 'Times New Roman', Times, serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                    <div style="background-color: #1b5e20; color: #ffffff; padding: 20px; text-align: center;">
                        <h2 style="margin: 0; color: #fbc02d;">KULTIVA</h2>
                        <p style="margin: 5px 0 0 0; font-size: 14px;">Official Soil Test Acknowledgment</p>
                    </div>
                    <div style="padding: 30px; color: #333333;">
                        <h3 style="color: #2e7d32;">Hello {request.user.username},</h3>
                        <p>We have successfully received your manual soil data request. Our laboratory team will review the information below and update your Digital Soil Health Card shortly.</p>
                        
                        <div style="background-color: #f9f9f9; border-left: 4px solid #fbc02d; padding: 15px; margin: 20px 0; border-radius: 5px;">
                            <h4 style="margin-top: 0; color: #1b5e20;">Submitted Details:</h4>
                            <ul style="list-style-type: none; padding: 0; margin: 0;">
                                <li style="padding-bottom: 8px;"><strong>Total Land Area:</strong> {land_area} Acres</li>
                                <li style="padding-bottom: 8px;"><strong>Previous Crop:</strong> {previous_crop}</li>
                                <li style="padding-bottom: 8px;"><strong>Status:</strong> <span style="color: #e65100; font-weight: bold;">Pending Admin Review</span></li>
                            </ul>
                        </div>
                        
                        <p style="font-size: 14px; color: #666;">Once approved, our AI engine will automatically sync with your new soil data to provide hyper-accurate crop recommendations.</p>
                        <p>Happy Farming!<br><strong>The Kultiva Team</strong></p>
                    </div>
                    <div style="background-color: #eeeeee; padding: 15px; text-align: center; font-size: 12px; color: #888888;">
                        &copy; 2026 Kultiva AgriTech. All rights reserved.
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Strip tags to create a plain-text fallback version for older email clients
            plain_message = strip_tags(html_message)

            # 5. Send the Email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'no-reply@kultiva.com',
                recipient_list=[request.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            # 6. Success notification
            messages.success(request, "Success! Your data is submitted and an email confirmation has been sent to your registered address.")
            
        except ValueError:
            messages.error(request, "Error: Please enter valid numbers for the land area and soil parameters.")
        except Exception as e:
            messages.error(request, f"Submission saved, but email could not be sent. Check internet connection. Error: {e}")

    return redirect('farmer_home')

# --- FARMER: MANAGE TRADE CONTRACTS ---
@login_required
def farmer_proposals(request):
    if request.user.role != User.Role.FARMER:
        messages.error(request, "Access Denied. Farmers only.")
        return redirect('index')

    # Fetch all proposals linked to this farmer
    all_proposals = DirectTradeProposal.objects.filter(farmer=request.user).select_related('listing', 'buyer').order_by('-created_at')

    # Pre-sort for the tabbed interface
    pending = all_proposals.filter(status='PENDING')
    accepted = all_proposals.filter(status='ACCEPTED')
    completed = all_proposals.filter(status='COMPLETED') # NEW: Fetch successful trades
    history = all_proposals.filter(status__in=['REJECTED', 'CANCELLED'])

    context = {
        'pending': pending,
        'accepted': accepted,
        'completed': completed, # NEW: Pass to template
        'history': history,
    }
    return render(request, 'farmer_proposals.html', context)

from django.utils import timezone
from datetime import timedelta

@login_required
def farmer_proposal_detail(request, proposal_id):
    if request.user.role != User.Role.FARMER:
        return redirect('index')
        
    proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, farmer=request.user)
    
    # Unpack the clean JSON specs for the UI
    formatted_specs = {k.replace('_', ' '): v for k, v in proposal.listing.specifications.items()}
    
    # 1. Check who initiated it
    is_buyer_initiated = proposal.message and "Requested Qty:" in proposal.message
    
    # --- ADD THE TIMER HERE FOR THE HTML TO SEE ---
    # 2. Calculate if 24 hours have passed
    time_elapsed = timezone.now() - proposal.created_at
    can_revoke = time_elapsed <= timedelta(hours=24)
    # ----------------------------------------------
    
    context = {
        'proposal': proposal,
        'listing': proposal.listing,
        'buyer': proposal.buyer,
        'formatted_specs': formatted_specs,
        'is_buyer_initiated': is_buyer_initiated,
        'can_revoke': can_revoke  # <-- Now the Waiter has the flag!
    }
    return render(request, 'farmer_proposal_detail.html', context)

from django.utils import timezone
from datetime import timedelta

@login_required
def farmer_respond_proposal(request, proposal_id):
    if request.method == 'POST' and request.user.role == User.Role.FARMER:
        proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, farmer=request.user)
        action = request.POST.get('action') # Can be 'ACCEPT', 'REJECT', or 'CANCEL'
        farmer_message = request.POST.get('farmer_message', '').strip()

        if proposal.status != 'PENDING':
            messages.error(request, "This proposal has already been processed.")
            return redirect('farmer_proposals')

        # --- NEW SECURITY ENFORCEMENT ENGINE ---
        # 1. Identify who initiated the proposal
        is_buyer_initiated = proposal.message and "Requested Qty:" in proposal.message

        # 2. THE MISSING MATH: Calculate if 24 hours have passed
        time_elapsed = timezone.now() - proposal.created_at
        can_revoke = time_elapsed <= timedelta(hours=24)

        # 3. Hard-block illegal actions
        if is_buyer_initiated and action == 'CANCEL':
            messages.error(request, "Security Alert: You cannot revoke a buyer's offer. Please Accept or Reject it.")
            return redirect('farmer_proposal_detail', proposal_id=proposal.id)
            
        if not is_buyer_initiated and action in ['ACCEPT', 'REJECT']:
            messages.error(request, "Security Alert: You cannot accept or reject your own outbound offer. You can only revoke (CANCEL) it.")
            return redirect('farmer_proposal_detail', proposal_id=proposal.id)
            
        # 4. THE MISSING BLOCKER: Enforce the 24-hour Time Lock in the backend
        if action == 'CANCEL' and not can_revoke:
            messages.error(request, "Time Expired: The 24-hour cancellation window has closed.")
            return redirect('farmer_proposal_detail', proposal_id=proposal.id)
        # ---------------------------------------

        # 1. HANDLE "REVOKE SENT OFFER" SCENARIO (Farmer sent it)
        if action == 'CANCEL':
            proposal.status = 'CANCELLED'
            proposal.save()
            
            if proposal.listing.status == 'HIDDEN':
                proposal.listing.status = 'ACTIVE'
                proposal.listing.save()
                
            messages.success(request, f"You have successfully revoked the trade proposal.")
            return redirect('farmer_proposals')

        # 2. HANDLE "BUYER SENT THE OFFER" SCENARIO (Accept/Reject)
        if action == 'ACCEPT':
            proposal.status = 'ACCEPTED'
            status_text = "ACCEPTED"
            status_color = "#2e7d32" 
            next_steps = "<strong>Next Steps:</strong> The farmer is preparing the QR Code. Please ensure you scan it upon physical pickup to release the funds."
        elif action == 'REJECT':
            proposal.status = 'REJECTED'
            status_text = "REJECTED"
            status_color = "#d32f2f" 
            next_steps = "This specific negotiation has been closed by the farmer."
        else:
            return redirect('farmer_proposals')

        proposal.save()

        # --- EMAIL NOTIFICATION TO BUYER ---
        buyer_email = proposal.buyer.email
        subject = f"Kultiva Trade Update: Proposal {status_text} - {proposal.listing.title}"
        html_message = f"""
        <html>
        <body style="font-family: 'Times New Roman', Times, serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 16px rgba(0,0,0,0.1);">
                <div style="background: {status_color}; color: #ffffff; padding: 25px; text-align: center;">
                    <h2 style="margin: 0; color: #ffffff; font-size: 26px; letter-spacing: 1px;">TRADE {status_text}</h2>
                    <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Digital Handshake Update</p>
                </div>
                <div style="padding: 30px; color: #333333;">
                    <p style="font-size: 16px;"><strong>{request.user.username}</strong> has reviewed the trade proposal for <strong>{proposal.listing.title}</strong>.</p>
                    
                    <div style="background-color: #f9f9f9; border-left: 4px solid {status_color}; padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <strong style="color: #555; font-size: 12px; text-transform: uppercase;">Message from Farmer:</strong><br>
                        <span style="font-size: 15px; font-style: italic;">"{farmer_message if farmer_message else 'No additional notes provided.'}"</span>
                    </div>
                    
                    <p style="margin-top: 20px; font-size: 15px; color: #1e293b;">{next_steps}</p>
                    <p style="margin-bottom: 0; margin-top: 30px;">Regards,<br><strong style="color: #1b5e20;">Kultiva Automated Escrow</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        from django.utils.html import strip_tags
        from django.core.mail import send_mail
        send_mail(
            subject=subject, message=strip_tags(html_message), from_email='admin@kultiva.com',
            recipient_list=[buyer_email], html_message=html_message, fail_silently=True
        )

        messages.success(request, f"You have {status_text.lower()} the proposal from {proposal.buyer.username}.")

    return redirect('farmer_proposal_detail', proposal_id=proposal.id)

# --- FARMER: QR CODE GENERATOR ENGINE ---
@login_required
def generate_trade_qr(request, proposal_id):
    if request.method == 'POST' and request.user.role == User.Role.FARMER:
        proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, farmer=request.user)
        
        # FIX: We temporarily removed 'and not proposal.qr_code' so it forces a new image!
        if proposal.status == 'ACCEPTED':
            try:
                # 1. Create a highly secure cryptographic token
                unique_token = str(uuid.uuid4())
                proposal.security_token = unique_token
                
                # 2. Inject your exact network IP Address
                laptop_ip = "10.219.33.240" 
                
                # 3. Create the clickable URL payload
                qr_payload = f"http://{laptop_ip}:8000/buyer/escrow-checkout/{proposal.id}/?token={unique_token}"
                
                # 4. Generate the actual Image
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
                qr.add_data(qr_payload)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="#1b5e20", back_color="white")
                
                # 5. Save the image to the Django Database (This will overwrite the old one)
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                file_name = f'kultiva_qr_contract_{proposal.id}.png'
                
                proposal.qr_code.save(file_name, File(buffer), save=True)
                
                messages.success(request, "Secure Handshake QR Code generated successfully. Please show this to the buyer upon pickup.")
            except Exception as e:
                messages.error(request, f"Error generating QR Code: {e}")
                
    return redirect('farmer_proposal_detail', proposal_id=proposal.id)

@login_required
def farmer_input_market(request):
    # 1. Security Check: Only Farmers should be buying inputs
    if request.user.role != User.Role.FARMER:
        messages.error(request, "Access Denied. Only registered Farmers can view the Input Marketplace.")
        return redirect('index')

    try:
        # 2. Base Query: Only Active Inputs (Hide Harvest Produce and Hidden/Out-of-stock items)
        products = MarketplaceListing.objects.filter(status='ACTIVE', wing='INPUT').select_related('listed_by')
        
        # 3. Extract GET parameters from the URL
        query = request.GET.get('q', '').strip()
        selected_categories = request.GET.getlist('category')
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        sort_by = request.GET.get('sort', 'newest')

        # 4. Apply Search Query (Search by Title, Brand, or even the Seller's Shop Name)
        if query:
            products = products.filter(
                Q(title__icontains=query) | 
                Q(variety_or_brand__icontains=query) |
                Q(listed_by__seller_profile__shop_name__icontains=query)
            )

        # 5. Apply Category Filters (Seeds, Fertilizers, etc.)
        if selected_categories:
            products = products.filter(category__in=selected_categories)

        # 6. Apply Price Range Filters
        if min_price and min_price.replace('.', '', 1).isdigit():
            products = products.filter(price__gte=float(min_price))
        if max_price and max_price.replace('.', '', 1).isdigit():
            products = products.filter(price__lte=float(max_price))

        # 7. Apply Sorting
        if sort_by == 'price_low':
            products = products.order_by('price')
        elif sort_by == 'price_high':
            products = products.order_by('-price')
        else:
            products = products.order_by('-created_at') # 'newest' is the default

        # 8. Enterprise Pagination (9 items per page for a clean 3x3 UI grid)
        paginator = Paginator(products, 9)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # 9. Pack it all up for the template
        context = {
            'products': page_obj,
            'selected_categories': selected_categories,
            'current_sort': sort_by,
            'search_query': query,
            'min_price': min_price,
            'max_price': max_price
        }
        
        return render(request, 'farmer_input_market.html', context)
        
    except Exception as e:
        # The ultimate safety net to prevent 500 Server Errors
        messages.error(request, f"An error occurred while loading the marketplace: {e}")
        return redirect('farmer_home')

@login_required
def farmer_input_detail(request, listing_id):
    # 1. Security Check: Only Farmers buy inputs
    if request.user.role != User.Role.FARMER:
        messages.error(request, "Access Denied. Only registered Farmers can view input details.")
        return redirect('index')

    try:
        # 2. Fetch the exact product. We ensure it's ACTIVE and belongs to the INPUT wing.
        product = get_object_or_404(MarketplaceListing, id=listing_id, status='ACTIVE', wing='INPUT')

        # 3. Unpack and clean the Magic Field (JSON Specifications)
        formatted_specs = {}
        if product.specifications:
            formatted_specs = {k.replace('_', ' '): v for k, v in product.specifications.items()}

        # --- 4. NEW: VERIFIED BUYER CHECK ---
        # Check if this farmer actually bought this item successfully
        has_purchased = EscrowTransaction.objects.filter(
            item_purchased=product,
            purchaser=request.user,
            payment_status='COMPLETED'
        ).exists()

        # 5. Pack it up for the template
        context = {
            'product': product,
            'formatted_specs': formatted_specs,
            'has_purchased': has_purchased, # Pass the boolean to the HTML
        }
        
        return render(request, 'farmer_input_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Could not load the product details: {e}")
        return redirect('farmer_input_market')
    
# Don't forget to import InputOrder at the top of your file!
# from .models import InputOrder

@login_required
def farmer_checkout(request, listing_id):
    if request.user.role != User.Role.FARMER:
        return redirect('index')

    product = get_object_or_404(MarketplaceListing, id=listing_id, status='ACTIVE', wing='INPUT')
    address = request.user.addresses.first()

    # Capture quantity from URL (e.g., ?qty=2), default to min order if not provided
    qty_str = request.GET.get('qty', product.min_order_quantity)
    try:
        qty = float(qty_str)
    except ValueError:
        qty = product.min_order_quantity

    # E-Commerce Math Engine
    subtotal = product.price * Decimal(str(qty))
    packaging_fee = Decimal('20.00')
    delivery_fee = Decimal('0.00') # Free delivery for now
    total = subtotal + packaging_fee + delivery_fee

    context = {
        'product': product,
        'qty': qty,
        'address': address,
        'subtotal': subtotal,
        'packaging_fee': packaging_fee,
        'total': total
    }
    return render(request, 'farmer_checkout.html', context)

@login_required
def process_input_order(request, listing_id):
    if request.method == 'POST' and request.user.role == User.Role.FARMER:
        try:
            with transaction.atomic():
                product = get_object_or_404(MarketplaceListing, id=listing_id, status='ACTIVE', wing='INPUT')
                qty = float(request.POST.get('quantity', 1))
                payment_mode = request.POST.get('payment_mode', 'UPI')
                
                # Math Engine
                price_decimal = Decimal(str(product.price))
                qty_decimal = Decimal(str(qty))
                subtotal = price_decimal * qty_decimal
                packaging_fee = Decimal('20.00')
                total_amount = subtotal + packaging_fee

                # 1. Deduct Stock
                product.available_stock -= qty
                if product.available_stock <= 0:
                    product.status = 'OUT_OF_STOCK'
                product.save()

                # 2. Database Record
                addr = request.user.addresses.first()
                addr_str = f"{addr.village}, {addr.district}, {addr.state} - {addr.pincode}" if addr else "Address Pending"

                order = InputOrder.objects.create(
                    farmer=request.user, product=product, quantity=qty,
                    total_amount=total_amount, payment_method=payment_mode,
                    delivery_address=addr_str
                )

                EscrowTransaction.objects.create(
                    item_purchased=product, vendor=product.listed_by,
                    purchaser=request.user, amount_paid=total_amount,
                    payment_status='COMPLETED', security_token=f"ORDER-{order.order_id}"
                )

                # --- 3. THE HIGHLY INTEGRATED HTML BILL ENGINE ---
                # We use the CSS tokens from templatemo-space-dynamic.css inside inline styles
                subject = f"Invoice: {order.order_id} - Kultiva Input Marketplace"
                
                # Determine Badge Color based on Payment Mode
                payment_color = "#1a73e8" if payment_mode == "CARD" else "#5f259f"
                
                html_invoice = f"""
                <html>
                <body style="font-family: 'Times New Roman', Times, serif; background-color: #f1f8e9; padding: 20px;">
                    <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border-top: 8px solid #1b5e20;">
                        
                        <div style="padding: 30px; background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); text-align: center; color: white;">
                            <h1 style="margin: 0; font-size: 32px; letter-spacing: 2px;">KULTIVA</h1>
                            <p style="margin: 5px 0 0 0; color: #fbc02d; font-weight: bold; text-transform: uppercase; font-size: 12px;">Digital Payment Receipt</p>
                        </div>

                        <div style="padding: 40px;">
                            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px;">
                                <div>
                                    <h4 style="margin: 0; color: #888; font-size: 12px; text-transform: uppercase;">Invoice To:</h4>
                                    <p style="margin: 5px 0; font-weight: bold; color: #1b5e20; font-size: 18px;">{request.user.username}</p>
                                    <p style="margin: 0; color: #666; font-size: 13px; line-height: 1.4;">{addr_str}</p>
                                </div>
                                <div style="text-align: right;">
                                    <h4 style="margin: 0; color: #888; font-size: 12px; text-transform: uppercase;">Order ID:</h4>
                                    <p style="margin: 5px 0; font-weight: bold; color: #333;">{order.order_id}</p>
                                    <span style="background: {payment_color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 10px; font-weight: bold;">{payment_mode} PAID</span>
                                </div>
                            </div>

                            <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
                                <thead>
                                    <tr style="background: #f9f9f9; text-align: left;">
                                        <th style="padding: 12px; border-bottom: 2px solid #1b5e20; color: #1b5e20; font-size: 14px;">Product Description</th>
                                        <th style="padding: 12px; border-bottom: 2px solid #1b5e20; color: #1b5e20; font-size: 14px; text-align: right;">Qty</th>
                                        <th style="padding: 12px; border-bottom: 2px solid #1b5e20; color: #1b5e20; font-size: 14px; text-align: right;">Amount</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td style="padding: 15px 12px; border-bottom: 1px solid #eee;">
                                            <p style="margin: 0; font-weight: bold; color: #333;">{product.title}</p>
                                            <p style="margin: 2px 0 0 0; font-size: 11px; color: #888;">Category: {product.get_category_display()}</p>
                                        </td>
                                        <td style="padding: 15px 12px; border-bottom: 1px solid #eee; text-align: right; color: #666;">{qty} {product.unit_of_measure}</td>
                                        <td style="padding: 15px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">₹{subtotal}</td>
                                    </tr>
                                </tbody>
                            </table>

                            <div style="margin-left: auto; width: 250px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                    <span style="color: #888;">Subtotal:</span>
                                    <span style="font-weight: bold;">₹{subtotal}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                    <span style="color: #888;">Packaging Fee:</span>
                                    <span style="font-weight: bold;">₹{packaging_fee}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-top: 15px; padding-top: 15px; border-top: 2px solid #fbc02d;">
                                    <span style="color: #1b5e20; font-weight: 900; font-size: 18px;">TOTAL:</span>
                                    <span style="color: #1b5e20; font-weight: 900; font-size: 18px;">₹{total_amount}</span>
                                </div>
                            </div>

                            <div style="margin-top: 50px; background: #fffde7; padding: 20px; border-radius: 10px; border-left: 5px solid #fbc02d;">
                                <p style="margin: 0; font-size: 13px; color: #856404; line-height: 1.5;">
                                    <strong>Important:</strong> Your payment is secured via the Kultiva Escrow Vault. Funds will only be released to the vendor once the delivery is verified.
                                </p>
                            </div>
                        </div>

                        <div style="background: #1d1d1f; color: #94a3b8; padding: 20px; text-align: center; font-size: 11px;">
                            &copy; 2026 Kultiva AI Agriculture Platform. All rights reserved.<br>
                            This is a system-generated secure invoice. No signature required.
                        </div>
                    </div>
                </body>
                </html>
                """

                # 4. Trigger Multi-Recipient Notifications
                # Recipient A: The Farmer (Buyer)
                send_mail(subject, strip_tags(html_invoice), 'billing@kultiva.com', [request.user.email], html_message=html_invoice, fail_silently=True)

                # Recipient B: The Seller (Order for Fulfillment)
                seller_subject = f"NEW ORDER: {order.order_id} - Dispatch Required"
                send_mail(seller_subject, f"New order received for {product.title}. Total: ₹{total_amount}", 'orders@kultiva.com', [product.listed_by.email], html_message=html_invoice, fail_silently=True)

                messages.success(request, f"Order {order.order_id} secured. Check your email for the detailed invoice.")
                return redirect('farmer_home')

        except Exception as e:
            messages.error(request, f"Transactional Error: {e}")
            return redirect('farmer_checkout', listing_id=listing_id)

    return redirect('farmer_input_market')

@login_required
def dummy_payment_gateway(request, listing_id):
    if request.method == 'POST' and request.user.role == User.Role.FARMER:
        try:
            product = get_object_or_404(MarketplaceListing, id=listing_id, status='ACTIVE', wing='INPUT')
            
            # Capture what they chose on the checkout page
            qty = float(request.POST.get('quantity', 1))
            payment_mode = request.POST.get('payment_mode', 'UPI')
            
            # Recalculate total for the Gateway UI
            total_amount = (product.price * Decimal(str(qty))) + Decimal('20.00')
            
            # If Cash on Delivery, skip the gateway and process the order immediately!
            if payment_mode == 'COD':
                return process_input_order(request, listing_id)
                
            # Otherwise, package the data and send them to the mockup
            context = {
                'product': product,
                'qty': qty,
                'total_amount': total_amount,
                'payment_mode': payment_mode
            }
            
            if payment_mode == 'UPI':
                return render(request, 'dummy_payment_upi.html', context)
            elif payment_mode == 'CARD':
                return render(request, 'dummy_payment_card.html', context)
                
        except Exception as e:
            messages.error(request, f"Gateway Error: {e}")
            return redirect('farmer_checkout', listing_id=listing_id)
            
    return redirect('farmer_input_market')

# --- FARMER: ORDER MANAGEMENT DASHBOARD ---
@login_required
def farmer_orders(request):
    # 1. Security Check
    if request.user.role != User.Role.FARMER:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        # 2. Base Query: Fetch orders for the logged-in farmer
        orders = InputOrder.objects.filter(farmer=request.user).select_related('product', 'product__listed_by').order_by('-created_at')

        # 3. Apply Search Filter
        query = request.GET.get('q', '').strip()
        if query:
            orders = orders.filter(
                Q(order_id__icontains=query) |
                Q(product__title__icontains=query)
            )

        # 4. Apply Tab Status Filter (NOW SYNCED WITH YOUR HTML TABS)
        status_filter = request.GET.get('status', 'all')
        
        if status_filter == 'pending':
            orders = orders.filter(status='PENDING')
        elif status_filter == 'transit':
            orders = orders.filter(status='SHIPPED')
        elif status_filter == 'delivered':
            orders = orders.filter(status='DELIVERED')
        elif status_filter == 'refunded':
            # PRO FIX: Explicitly listen for your new Refunded tab!
            orders = orders.filter(status='REFUNDED')
        elif status_filter == 'cancelled':
            # PRO FIX: Only show strictly cancelled (pending refund) items here
            orders = orders.filter(status='CANCELLED')

        context = {
            'orders': orders,
            'current_status': status_filter,
            'search_query': query
        }
        return render(request, 'farmer_orders.html', context)

    except Exception as e:
        messages.error(request, f"Error loading orders: {e}")
        return redirect('farmer_home')
    
# Helper Function: Number to Words (Industry Standard)
def amount_to_words(number):
    from num2words import num2words # Make sure to 'pip install num2words'
    try:
        words = num2words(number, lang='en_IN').replace(',', '')
        return f"Rupees {words.title()} Only"
    except:
        return f"Rupees {number} Only"

@login_required
def farmer_invoice_detail(request, order_id):
    # 1. Security Check
    if request.user.role != User.Role.FARMER:
        return redirect('index')

    try:
        # 2. Fetch the Order and related data
        order = get_object_or_404(InputOrder, order_id=order_id, farmer=request.user)
        product = order.product
        seller = product.listed_by
        seller_profile = getattr(seller, 'seller_profile', None)
        farmer_address = request.user.addresses.first()

        # 3. Industry Standard Tax Engine (GST Slabs)
        # Seeds/Fertilizers: 5%, Agrochemicals: 12%, Machinery/Tools: 18%
        gst_rate = 18 
        if product.category in ['SEEDS', 'FERTILIZERS']: gst_rate = 5
        elif product.category in ['AGROCHEMICALS', 'TOOLS']: gst_rate = 12

        # Reverse Calculate for Tax Invoice (Assuming total_amount is inclusive)
        packaging_fee = Decimal('20.00')
        price_without_pkg = order.total_amount - packaging_fee
        tax_multiplier = Decimal(str(1 + (gst_rate / 100)))
        
        taxable_value = price_without_pkg / tax_multiplier
        total_gst = price_without_pkg - taxable_value
        cgst = total_gst / 2
        sgst = total_gst / 2

        context = {
            'order': order,
            'product': product,
            'seller': seller,
            'seller_profile': seller_profile,
            'farmer_address': farmer_address,
            'taxable_value': round(taxable_value, 2),
            'cgst': round(cgst, 2),
            'sgst': round(sgst, 2),
            'gst_rate_half': gst_rate / 2,
            'packaging_fee': packaging_fee,
            'amount_in_words': amount_to_words(order.total_amount)
        }
        
        return render(request, 'farmer_invoice_detail.html', context)

    except Exception as e:
        messages.error(request, f"Invoice generation failed: {e}")
        return redirect('farmer_orders')

from django.core.mail import send_mail
from django.utils.html import strip_tags

from django.utils import timezone
import datetime

@login_required
def farmer_order_details(request, order_id):
    if request.user.role != User.Role.FARMER:
        messages.error(request, "Access Denied.")
        return redirect('index')

    # Fetch the order securely
    order = get_object_or_404(InputOrder, order_id=order_id, farmer=request.user)
    
    # --- 1. TIME CONSTRAINT LOGIC (24 Hour Window) ---
    time_elapsed = timezone.now() - order.created_at
    is_cancel_window_open = time_elapsed.total_seconds() <= 86400 # 86400 seconds = 24 hours
    
    # --- 2. EXISTING FEEDBACK CHECK ---
    existing_review = UnifiedReview.objects.filter(input_order=order).first()

    if request.method == 'POST':
        action = request.POST.get('action')

        # --- ACTION A: CANCELLATION LOGIC ---
        if action == 'cancel_order':
            if order.status in ['DELIVERED', 'CANCELLED']:
                messages.error(request, "This order cannot be cancelled.")
                return redirect('farmer_order_details', order_id=order_id)
                
            # Enforce the 24-hour rule strictly on the backend!
            if not is_cancel_window_open:
                messages.error(request, "The 24-hour cancellation window has expired for this order.")
                return redirect('farmer_order_details', order_id=order_id)

            reason = request.POST.get('cancel_reason', 'No reason provided.')
            
            # Update Database
            order.status = 'CANCELLED'
            order.save()

            # Prepare Emails
            subject = f"Order Cancelled: {order.order_id}"
            farmer_msg = f"Dear {order.farmer.username},\n\nYour cancellation for {order.product.title} has been recorded.\nReason: {reason}\n\nOur Admin team will verify this request and initiate your refund (if applicable) within 3-5 business days."
            seller_msg = f"Dear {order.product.listed_by.username},\n\nThe buyer has cancelled the order {order.order_id} for {order.product.title}.\nReason provided: {reason}\n\nPlease halt any dispatch processes. Admin will handle any Escrow/Payment reversals."

            # Dispatch Emails to both parties
            send_mail(subject, farmer_msg, 'admin@kultiva.com', [order.farmer.email], fail_silently=True)
            send_mail(subject, seller_msg, 'admin@kultiva.com', [order.product.listed_by.email], fail_silently=True)

            messages.success(request, "Order cancelled successfully. Admin has been notified to process your refund.")
            return redirect('farmer_order_details', order_id=order_id)

        # --- ACTION B: UNIFIED FEEDBACK LOGIC ---
        elif action == 'submit_feedback':
            # Defensive check: block duplicate submissions
            if existing_review:
                messages.warning(request, "You have already submitted feedback for this transaction.")
                return redirect('farmer_order_details', order_id=order_id)
                
            rating = request.POST.get('rating')
            description = request.POST.get('description', '').strip()

            try:
                # Save directly to our Unified Trust table!
                UnifiedReview.objects.create(
                    reviewer=request.user,
                    reviewee=order.product.listed_by,
                    rating=int(rating),
                    comment=description,
                    input_order=order
                )
                messages.success(request, "Thank you! Your feedback has been published to the seller's portfolio.")
            except Exception as e:
                messages.error(request, f"Error saving feedback: {e}")
                
            return redirect('farmer_order_details', order_id=order_id)

    context = {
        'order': order,
        'is_cancel_window_open': is_cancel_window_open,
        'existing_review': existing_review
    }
    return render(request, 'farmer_order_details.html', context)

from django.db.models import Avg, Count, Sum, Q
from django.db.models.functions import Coalesce

# --- 1. THE SELLER DIRECTORY & RANKING ENGINE ---
@login_required
def farmer_seller_list(request):
    if request.user.role != User.Role.FARMER:
        messages.error(request, "Access Denied. Farmers only.")
        return redirect('index')

    try:
        # THE AMAZON ALGORITHM: 
        # Fetch Active Sellers -> Calculate Average Rating -> Count Total Sales -> Sort them!
        sellers = User.objects.filter(
            role=User.Role.SELLER,
            is_verified=True,
            is_active=True
        ).select_related('seller_profile').prefetch_related('addresses').annotate(
            # Calculate Average Rating (If no reviews, default to 0.0)
            avg_rating=Coalesce(Avg('reviews_received__rating'), 0.0),
            
            # Count total number of reviews
            total_reviews=Count('reviews_received', distinct=True),
            
            # Count total number of successfully completed sales using Escrow history
            total_sales=Count('sales_received', filter=Q(sales_received__payment_status='COMPLETED'), distinct=True)
            
        ).order_by('-avg_rating', '-total_sales', '-date_joined')

        # Add a Search Engine
        search_query = request.GET.get('q', '').strip()
        if search_query:
            sellers = sellers.filter(
                Q(username__icontains=search_query) |
                Q(seller_profile__shop_name__icontains=search_query) |
                Q(addresses__district__icontains=search_query)
            ).distinct()

        context = {
            'sellers': sellers,
            'search_query': search_query
        }
        return render(request, 'farmer_seller_list.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading seller network: {e}")
        return redirect('farmer_home')


# --- 2. THE AMAZON-STYLE STOREFRONT ---
@login_required
def farmer_view_seller_profile(request, seller_id):
    if request.user.role != User.Role.FARMER:
        return redirect('index')

    try:
        # 1. Fetch the Seller with their exact metrics
        seller = get_object_or_404(
            User.objects.select_related('seller_profile').annotate(
                avg_rating=Coalesce(Avg('reviews_received__rating'), 0.0),
                total_reviews=Count('reviews_received', distinct=True),
                total_sales=Count('sales_received', filter=Q(sales_received__payment_status='COMPLETED'), distinct=True)
            ), 
            user_id=seller_id, 
            role=User.Role.SELLER, 
            is_verified=True
        )
        
        address = seller.addresses.first()
        
        # 2. Fetch the Seller's Active Inventory
        products = MarketplaceListing.objects.filter(
            listed_by=seller, 
            status='ACTIVE', 
            wing='INPUT'
        ).order_by('-created_at')
        
        # 3. Fetch Public Feedback / Reviews
        reviews = UnifiedReview.objects.filter(
            reviewee=seller
        ).select_related('reviewer', 'input_order__product').order_by('-created_at')
        
        context = {
            'seller': seller,
            'address': address,
            'products': products,
            'reviews': reviews
        }
        return render(request, 'farmer_view_seller_profile.html', context)
        
    except Exception as e:
        messages.error(request, f"Could not load storefront: {e}")
        return redirect('farmer_seller_list')

# --- BUYER DASHBOARD ---
@login_required
def buyer_dashboard(request):
    # Ensure only verified Buyers can access this dashboard
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied. Only registered Buyers can view this page.")
        return redirect('index')
        
    context = {
        # We will pass wallet balances and active orders here in the future!
    }
    return render(request, 'buyer_dashboard.html', context)


# --- BUYER MARKETPLACE ---
@login_required
def buyer_marketplace(request):
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied. Only registered Buyers can view the marketplace.")
        return redirect('index')
    
    # 1. Base Query: ONLY show Farm Produce (Hide Sellers' tools/seeds)
    products = MarketplaceListing.objects.filter(status='ACTIVE', wing='PRODUCE')
    
    # 2. Extract GET parameters
    query = request.GET.get('q', '').strip()
    selected_categories = request.GET.getlist('category') 
    is_organic = request.GET.get('organic') == 'true'
    sort_by = request.GET.get('sort', 'newest')

    # 3. Apply Search Query
    if query:
        products = products.filter(
            Q(title__icontains=query) | 
            Q(variety_or_brand__icontains=query) |
            Q(listed_by__addresses__district__icontains=query)
        )

    # 4. Apply Category Filters
    if selected_categories:
        products = products.filter(category__in=selected_categories)

    # 5. Apply Organic Filter
    if is_organic:
        products = products.filter(is_organic=True)

    # 6. Apply Sorting
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    else:
        products = products.order_by('-created_at')

    # 7. Pagination
    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj, 
        'category_choices': MarketplaceListing.CATEGORY_CHOICES, 
        'selected_categories': selected_categories, 
    }
    
    return render(request, 'buyer_marketplace.html', context)

# --- 1. VIEW THE LISTING DETAIL ---
@login_required
def buyer_product_detail(request, listing_id):
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied. Only registered Buyers can view product details.")
        return redirect('index')
        
    listing = get_object_or_404(MarketplaceListing, pk=listing_id, status='ACTIVE')
    
    # Optional: Fetch the farmer's soil report to show a "Lab Verified" trust badge
    soil_report = ManualSoilReport.objects.filter(farmer=listing.listed_by, request_status='COMPLETED').first()
    
    # Check if this buyer has already sent a proposal for this item
    existing_proposal = DirectTradeProposal.objects.filter(listing=listing, buyer=request.user).first()
    
    formatted_specs = {k.replace('_', ' '): v for k, v in listing.specifications.items()}
    
    context = {
        'item': listing,
        'soil_report': soil_report,
        'existing_proposal': existing_proposal
    }
    return render(request, 'buyer_product_detail.html', context)

# --- 2. HANDLE THE BUYER'S PROPOSAL REQUEST ---
@login_required
def submit_buyer_proposal(request, listing_id):
    if request.method == 'POST' and request.user.role == User.Role.BUYER:
        try:
            listing = get_object_or_404(MarketplaceListing, pk=listing_id, status='ACTIVE')
            
            # Capture the negotiation details from the modal
            proposed_qty = request.POST.get('proposed_qty')
            proposed_price = request.POST.get('proposed_price')
            custom_note = request.POST.get('message', '').strip()
            
            # Combine them into the single message field we created in the database
            full_message = f"Requested Qty: {proposed_qty} {listing.unit_of_measure} | Offer Price: ₹{proposed_price}/{listing.unit_of_measure} | Note: {custom_note}"

            # Create the 3NF Proposal
            proposal, created = DirectTradeProposal.objects.get_or_create(
                listing=listing,
                farmer=listing.listed_by,
                buyer=request.user,
                defaults={'message': full_message, 'status': 'PENDING'}
            )
            
            if not created:
                messages.error(request, "You already have a pending proposal for this harvest. Await the farmer's response.")
                return redirect('buyer_product_detail', listing_id=listing_id)
            
            # --- EMAIL 1: To the Farmer (Notification) ---
            farmer_html = f"""
            <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
                <h2 style="color: #2e7d32;">New Trade Offer Received!</h2>
                <p><strong>{request.user.username}</strong> has initiated a digital handshake for your harvest.</p>
                <div style="background: #f1f8e9; padding: 15px; border-left: 4px solid #fbc02d; border-radius: 5px;">
                    <h3>{listing.title}</h3>
                    <p><strong>Buyer's Offer:</strong> {full_message}</p>
                </div>
                <p>Please log in to your Farmer Dashboard to Accept or Reject this offer.</p>
            </div>
            """
            send_mail(
                f"New Offer: {listing.title}", strip_tags(farmer_html), 'admin@kultiva.com',
                [listing.listed_by.email], html_message=farmer_html, fail_silently=True
            )
            
            # --- EMAIL 2: To the Buyer (Receipt) ---
            buyer_html = f"""
            <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
                <h2 style="color: #1b5e20;">Proposal Sent Successfully</h2>
                <p>Your official trade request for <strong>{listing.title}</strong> has been forwarded to the farmer.</p>
                <p>Once accepted, a unique QR Code will be generated for verifiable pickup and payment.</p>
            </div>
            """
            send_mail(
                f"Proposal Receipt: {listing.title}", strip_tags(buyer_html), 'admin@kultiva.com',
                [request.user.email], html_message=buyer_html, fail_silently=True
            )

            messages.success(request, f"Trade proposal successfully sent to {listing.listed_by.username}! They will review your offer shortly.")
            
        except Exception as e:
            messages.error(request, f"Error processing proposal: {e}")
            
    return redirect('buyer_product_detail', listing_id=listing_id)

# --- BUYER: MANAGE TRADE PROPOSALS ---
@login_required
def buyer_proposals(request):
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied. Buyers only.")
        return redirect('index')

    # Fetch all proposals linked to this buyer
    all_proposals = DirectTradeProposal.objects.filter(buyer=request.user).select_related('listing', 'farmer').order_by('-created_at')

    # Pre-sort for the tabbed interface
    pending = all_proposals.filter(status='PENDING')
    accepted = all_proposals.filter(status='ACCEPTED')
    history = all_proposals.filter(status__in=['REJECTED', 'CANCELLED'])

    context = {
        'pending': pending,
        'accepted': accepted,
        'history': history,
    }
    return render(request, 'buyer_proposals.html', context)

# --- BUYER: PROPOSAL DETAIL (UPGRADED) ---
# --- BUYER: PROPOSAL DETAIL (UPGRADED WITH TIMERS) ---
from django.utils import timezone
from datetime import timedelta

@login_required
def buyer_proposal_detail(request, proposal_id):
    if request.user.role != User.Role.BUYER:
        return redirect('index')
        
    proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
    listing = proposal.listing
    
    # Clean the JSON specifications for display
    formatted_specs = {k.replace('_', ' '): v for k, v in listing.specifications.items()}
    
    # --- NEW: Identify who initiated and set the 24hr timer ---
    is_buyer_initiated = proposal.message and "Requested Qty:" in proposal.message
    time_elapsed = timezone.now() - proposal.created_at
    can_revoke = time_elapsed <= timedelta(hours=24)
    
    context = {
        'proposal': proposal,
        'listing': listing,
        'farmer': proposal.farmer,
        'formatted_specs': formatted_specs,
        'is_buyer_initiated': is_buyer_initiated, # <-- Pass the flag!
        'can_revoke': can_revoke                  # <-- Pass the timer!
    }
    return render(request, 'buyer_proposal_detail.html', context)


# --- BUYER: ACCEPT / REJECT / CANCEL ACTION (SECURITY ENGINE) ---
@login_required
def respond_to_proposal(request, proposal_id):
    if request.method == 'POST' and request.user.role == User.Role.BUYER:
        proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
        action = request.POST.get('action') # 'ACCEPT', 'REJECT', or 'CANCEL'
        buyer_message = request.POST.get('buyer_message', '').strip()

        # Security check: Make sure it hasn't already been processed
        if proposal.status != 'PENDING':
            messages.error(request, "This proposal has already been processed.")
            return redirect('buyer_proposals')

        # --- NEW SECURITY ENFORCEMENT ENGINE ---
        is_buyer_initiated = proposal.message and "Requested Qty:" in proposal.message
        time_elapsed = timezone.now() - proposal.created_at
        can_revoke = time_elapsed <= timedelta(hours=24)

        # Hard-block illegal actions
        if not is_buyer_initiated and action == 'CANCEL':
            messages.error(request, "Security Alert: You cannot revoke a farmer's offer. Please Accept or Reject it.")
            return redirect('buyer_proposal_detail', proposal_id=proposal.id)
            
        if is_buyer_initiated and action in ['ACCEPT', 'REJECT']:
            messages.error(request, "Security Alert: You cannot accept or reject your own outbound offer. You can only revoke (CANCEL) it.")
            return redirect('buyer_proposal_detail', proposal_id=proposal.id)
            
        if action == 'CANCEL' and not can_revoke:
            messages.error(request, "Time Expired: The 24-hour cancellation window has closed.")
            return redirect('buyer_proposal_detail', proposal_id=proposal.id)
        # ---------------------------------------

        # 1. HANDLE "REVOKE SENT OFFER" SCENARIO (Buyer sent it)
        if action == 'CANCEL':
            proposal.status = 'CANCELLED'
            proposal.save()
            messages.success(request, "You have successfully revoked your trade proposal.")
            return redirect('buyer_proposals')

        # 2. HANDLE "FARMER SENT THE OFFER" SCENARIO (Accept/Reject)
        if action == 'ACCEPT':
            proposal.status = 'ACCEPTED'
            status_text = "ACCEPTED"
            status_color = "#2e7d32" # Green
            next_steps = "<strong>Next Steps:</strong> A secure QR Code is now pending generation on your dashboard. The buyer will scan this upon physical pickup to release funds."
        elif action == 'REJECT':
            proposal.status = 'REJECTED'
            status_text = "REJECTED"
            status_color = "#d32f2f" # Red
            next_steps = "This specific negotiation has been closed by the buyer."
        else:
            return redirect('buyer_proposals')

        proposal.save()

        # --- EMAIL TO FARMER ---
        farmer_email = proposal.farmer.email
        subject = f"Kultiva Trade Update: Proposal {status_text} - {proposal.listing.title}"
        html_message = f"""
        <html>
        <body style="font-family: 'Times New Roman', Times, serif; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 16px rgba(0,0,0,0.1);">
                <div style="background: {status_color}; color: #ffffff; padding: 25px; text-align: center;">
                    <h2 style="margin: 0; color: #ffffff; font-size: 26px; letter-spacing: 1px;">TRADE {status_text}</h2>
                    <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Digital Handshake Update</p>
                </div>
                <div style="padding: 30px; color: #333333;">
                    <p style="font-size: 16px;"><strong>{request.user.username}</strong> has reviewed your trade proposal for <strong>{proposal.listing.title}</strong>.</p>
                    
                    <div style="background-color: #f9f9f9; border-left: 4px solid {status_color}; padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <strong style="color: #555; font-size: 12px; text-transform: uppercase;">Message from Buyer:</strong><br>
                        <span style="font-size: 15px; font-style: italic;">"{buyer_message if buyer_message else 'No additional notes provided.'}"</span>
                    </div>
                    
                    <p style="margin-top: 20px; font-size: 15px; color: #1e293b;">{next_steps}</p>
                    <p style="margin-bottom: 0; margin-top: 30px;">Regards,<br><strong style="color: #1b5e20;">Kultiva Automated Escrow</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        from django.utils.html import strip_tags
        send_mail(
            subject=subject,
            message=strip_tags(html_message),
            from_email='admin@kultiva.com',
            recipient_list=[farmer_email],
            html_message=html_message,
            fail_silently=True
        )

        messages.success(request, f"You have {status_text.lower()} the proposal. An email has been sent to {proposal.farmer.username}.")

    return redirect('buyer_proposals')

# --- BUYER: 1. IN-APP QR SCANNER ---
@login_required
def buyer_scan_qr(request):
    if request.user.role != User.Role.BUYER:
        return redirect('index')
    return render(request, 'buyer_scan_qr.html')

# --- BUYER: 2. ESCROW CHECKOUT PAGE ---
@login_required
def buyer_escrow_checkout(request, proposal_id):
    if request.user.role != User.Role.BUYER:
        return redirect('index')
        
    proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
    
    # SECURITY: Verify the cryptographic token from the URL
    url_token = request.GET.get('token')
    if proposal.security_token != url_token:
        messages.error(request, "SECURITY ALERT: Invalid or expired QR Token. Payment blocked.")
        return redirect('buyer_dashboard')
        
    if proposal.status == 'COMPLETED' or proposal.is_paid:
        messages.warning(request, "This contract has already been paid and completed.")
        return redirect('buyer_proposals')

    # Calculate Total
    total_amount = proposal.listing.price * Decimal(str(proposal.listing.available_stock))
    
    context = {
        'proposal': proposal,
        'listing': proposal.listing,
        'total_amount': total_amount
    }
    return render(request, 'buyer_escrow_checkout.html', context)

# --- BUYER: 3. PROCESS PAYMENT & DEDUCT INVENTORY ---
@login_required
def process_payment(request, proposal_id):
    if request.method == 'POST' and request.user.role == User.Role.BUYER:
        try:
            with transaction.atomic():
                proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
                listing = proposal.listing
                
                if proposal.is_paid:
                    messages.error(request, "Payment already processed.")
                    return redirect('buyer_proposals')

                # 1. Update Proposal Status
                proposal.is_paid = True
                proposal.status = 'COMPLETED'
                proposal.save()

                # 2. Deduct the sold stock
                total_amount = listing.price * Decimal(str(listing.available_stock if listing.available_stock > 0 else 1))
                listing.available_stock = 0 
                listing.status = 'OUT_OF_STOCK'
                listing.save()

                # --- 3. NEW: CREATE THE UNIVERSAL ORDER RECEIPT ---
                EscrowTransaction.objects.create(
                    item_purchased=listing,
                    vendor=listing.listed_by,
                    purchaser=request.user,
                    amount_paid=total_amount,
                    payment_status='COMPLETED',
                    security_token=proposal.security_token
                )
                # --------------------------------------------------

                # 4. Send Final Receipt Emails
                receipt_html = f"""
                <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
                    <h2 style="color: #2e7d32;">Trade Completed Successfully</h2>
                    <p>The digital handshake for <strong>{listing.title}</strong> is complete.</p>
                    <div style="background: #f1f8e9; padding: 15px; border-left: 4px solid #2e7d32;">
                        <h3>Payment Released to Escrow</h3>
                        <p><strong>Amount:</strong> ₹{total_amount}</p>
                        <p><strong>Farmer:</strong> {listing.listed_by.username}</p>
                        <p><strong>Buyer:</strong> {request.user.username}</p>
                    </div>
                </div>
                """
                send_mail(f"Receipt: {listing.title}", strip_tags(receipt_html), 'admin@kultiva.com', [request.user.email], html_message=receipt_html, fail_silently=True)
                send_mail(f"Funds Released: {listing.title}", strip_tags(receipt_html), 'admin@kultiva.com', [listing.listed_by.email], html_message=receipt_html, fail_silently=True)

                messages.success(request, f"Payment of ₹{total_amount} successful! The crop ownership has been transferred.")
                return redirect('buyer_proposals')
                
        except Exception as e:
            messages.error(request, f"Payment failed: {e}")
            
    return redirect('buyer_proposals')

# --- BUYER: ESCROW TRACKING & FUNDING ---
@login_required
def buyer_escrow_list(request):
    if request.user.role != User.Role.BUYER:
        return redirect('index')
    
    # Fetch all contracts where the farmer has accepted the deal
    deliveries = DirectTradeProposal.objects.filter(buyer=request.user, status='ACCEPTED').order_by('-created_at')
    return render(request, 'buyer_escrow_list.html', {'deliveries': deliveries})

@login_required
def buyer_escrow_detail(request, proposal_id):
    if request.user.role != User.Role.BUYER:
        return redirect('index')
        
    proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
    
    # Calculate Total Amount
    total_amount = proposal.listing.price * Decimal(str(proposal.listing.available_stock if proposal.listing.available_stock > 0 else 1))
    
    # Unpack JSON specifications safely
    formatted_specs = {k.replace('_', ' '): v for k, v in proposal.listing.specifications.items()}

    context = {
        'proposal': proposal,
        'listing': proposal.listing,
        'total_amount': total_amount,
        'formatted_specs': formatted_specs
    }
    return render(request, 'buyer_escrow_detail.html', context)

@login_required
def fund_escrow(request, proposal_id):
    if request.method == 'POST' and request.user.role == User.Role.BUYER:
        try:
            with transaction.atomic():
                proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
                
                if proposal.is_paid:
                    messages.warning(request, "These funds are already locked in Escrow.")
                    return redirect('buyer_escrow_list')
                    
                total_amount = proposal.listing.price * Decimal(str(proposal.listing.available_stock if proposal.listing.available_stock > 0 else 1))
                
                # 1. Mark as funded (but NOT completed yet!)
                proposal.is_paid = True
                proposal.save()
                
                # 2. Create Universal Order Receipt (Status: ESCROW_LOCKED)
                EscrowTransaction.objects.create(
                    item_purchased=proposal.listing,
                    vendor=proposal.listing.listed_by,
                    purchaser=request.user,
                    amount_paid=total_amount,
                    payment_status='ESCROW_LOCKED',
                    security_token=proposal.security_token
                )
                
                # 3. Notify the Farmer to dispatch the goods
                farmer_html = f"""
                <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px;">
                    <h2 style="color: #2e7d32;">Funds Locked in Escrow!</h2>
                    <p>The buyer has successfully deposited <strong>₹{total_amount}</strong> into the Kultiva Escrow Vault for <strong>{proposal.listing.title}</strong>.</p>
                    <div style="background: #fff8e1; border-left: 4px solid #fbc02d; padding: 15px; margin: 20px 0;">
                        <strong>Action Required:</strong> Please dispatch the goods. The funds will be automatically released to your account the moment the buyer scans your QR Code upon physical delivery.
                    </div>
                </div>
                """
                send_mail(f"Escrow Funded: {proposal.listing.title}", strip_tags(farmer_html), 'admin@kultiva.com', [proposal.listing.listed_by.email], html_message=farmer_html, fail_silently=True)
                
                messages.success(request, f"₹{total_amount} successfully locked in Escrow. The farmer has been notified to dispatch.")
        except Exception as e:
            messages.error(request, f"Escrow Funding failed: {e}")
            
    return redirect('buyer_escrow_list')

# --- BUYER: ESCROW DISPUTE & REFUND REQUEST ---
@login_required
def request_refund(request, proposal_id):
    if request.method == 'POST' and request.user.role == User.Role.BUYER:
        try:
            proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
            reason = request.POST.get('reason')
            description = request.POST.get('description', '').strip()
            
            # Retrieve the exact transaction receipt
            escrow_txn = EscrowTransaction.objects.filter(
                item_purchased=proposal.listing, 
                purchaser=request.user,
                payment_status='ESCROW_LOCKED'
            ).first()
            
            txn_id = escrow_txn.transaction_id if escrow_txn else "N/A"
            amount = escrow_txn.amount_paid if escrow_txn else "Unknown"

            # Escalate to Platform Admin for Verification
            admin_html = f"""
            <div style="font-family: Arial; padding: 20px; border: 1px solid #d32f2f; border-radius: 10px;">
                <h2 style="color: #d32f2f;">URGENT: Escrow Dispute / Refund Request</h2>
                <p>A buyer has requested a refund for locked escrow funds. Investigation required.</p>
                <div style="background: #ffebee; padding: 15px; border-left: 4px solid #d32f2f;">
                    <p><strong>Transaction ID:</strong> {txn_id}</p>
                    <p><strong>Amount Locked:</strong> ₹{amount}</p>
                    <p><strong>Contract Ref:</strong> KUL-{proposal.id}</p>
                    <p><strong>Buyer:</strong> {request.user.username}</p>
                    <p><strong>Vendor (Farmer):</strong> {proposal.farmer.username}</p>
                    <hr>
                    <p><strong>Dispute Reason:</strong> {reason}</p>
                    <p><strong>Details:</strong> {description}</p>
                </div>
                <p>Please log in to the Admin Dashboard to verify the claims and release/refund the funds accordingly.</p>
            </div>
            """
            
            # Send alert to Admin
            send_mail(
                f"DISPUTE ALERT: Contract KUL-{proposal.id}", 
                strip_tags(admin_html), 
                'admin@kultiva.com', 
                ['admin@kultiva.com'], # In production, this goes to your support team
                html_message=admin_html, 
                fail_silently=True
            )
            
            # Notify the Buyer
            messages.info(request, "Your refund request has been escalated to the Kultiva Admin team. We will verify the details with the farmer and process the resolution within 24 hours.")
            
        except Exception as e:
            messages.error(request, f"Error processing dispute: {e}")
            
    return redirect('buyer_escrow_detail', proposal_id=proposal.id)

# --- BUYER: NEGOTIATION HUB (INBOUND & OUTBOUND) ---
@login_required
def buyer_negotiations(request):
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied. Only registered Buyers can view negotiations.")
        return redirect('index')

    # Fetch every single proposal involving this specific buyer
    all_proposals = DirectTradeProposal.objects.filter(buyer=request.user).select_related('listing', 'farmer')

    # OUTBOUND (Bids Sent): The listing is owned by the Farmer. 
    # Therefore, the buyer is the one who found the crop and initiated the bid.
    sent_bids = all_proposals.exclude(listing__listed_by=request.user).order_by('-created_at')

    # INBOUND (Offers Received): The listing is owned by the Buyer (a Requirement post).
    # Therefore, the farmer saw the requirement and pitched their crop to the buyer.
    received_offers = all_proposals.filter(listing__listed_by=request.user).order_by('-created_at')

    context = {
        'sent_bids': sent_bids,
        'received_offers': received_offers,
    }
    
    return render(request, 'buyer_negotiations.html', context)

# --- BUYER: PURCHASE HISTORY & LEDGER ---
@login_required
def buyer_purchase_history(request):
    # 1. Security Gate: Only verified buyers
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied. Buyers only.")
        return redirect('index')

    try:
        # 2. Fetch all escrow transactions for this specific buyer
        # Using select_related to prevent N+1 database query issues
        all_txns = EscrowTransaction.objects.filter(
            purchaser=request.user
        ).select_related('item_purchased', 'vendor').order_by('-created_at')

        # 3. Categorize the funds based on status
        locked_funds = all_txns.filter(payment_status='ESCROW_LOCKED')
        completed_funds = all_txns.filter(payment_status='COMPLETED')
        refunded_funds = all_txns.filter(payment_status='REFUNDED')

        # 4. Math Engine: Calculate Total Values for the UI Metric Cards
        total_locked = locked_funds.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        total_completed = completed_funds.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')

        # 5. Pack everything for the HTML template
        context = {
            'locked_funds': locked_funds,
            'completed_funds': completed_funds,
            'refunded_funds': refunded_funds,
            'total_locked': total_locked,
            'total_completed': total_completed,
        }
        return render(request, 'buyer_purchase_history.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading purchase ledger: {e}")
        return redirect('buyer_dashboard')
# --- 1. UPDATED DIGITAL INVOICE VIEW (WITH FALLBACK) ---
@login_required
def buyer_invoice_detail(request, transaction_id):
    if request.user.role != User.Role.BUYER:
        return redirect('index')
        
    txn = get_object_or_404(EscrowTransaction, transaction_id=transaction_id, purchaser=request.user)
    listing = txn.item_purchased
    
    formatted_specs = {}
    if listing and listing.specifications:
        formatted_specs = {k.replace('_', ' '): v for k, v in listing.specifications.items()}

    # --- THE TRUST ENGINE CHECK ---
    b2b_trade = None
    if txn.security_token:
        # 1. Try to find by token (New Transactions)
        b2b_trade = DirectTradeProposal.objects.filter(security_token=txn.security_token).first()
        
    if not b2b_trade and listing:
        # 2. FALLBACK FOR OLD TRANSACTIONS (Before we added tokens)
        b2b_trade = DirectTradeProposal.objects.filter(listing=listing, buyer=request.user).first()
    
    existing_review = None
    if b2b_trade:
        existing_review = UnifiedReview.objects.filter(b2b_trade=b2b_trade).first()

    context = {
        'txn': txn,
        'buyer': request.user,
        'vendor': txn.vendor,
        'listing': listing,
        'formatted_specs': formatted_specs,
        'subtotal': txn.amount_paid,
        'platform_fee': "0.00",
        'total': txn.amount_paid,
        'existing_review': existing_review, 
    }
    
    return render(request, 'buyer_invoice_detail.html', context)


# --- 2. NEW UNIFIED REVIEW ENGINE (WITH EMAIL NOTIFICATION) ---
# --- 2. NEW UNIFIED REVIEW ENGINE (ULTIMATE FALLBACK + EMAIL) ---
@login_required
def submit_unified_review(request):
    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()

        try:
            # 1. Fetch the transaction securely
            txn = get_object_or_404(EscrowTransaction, transaction_id=transaction_id)

            if request.user != txn.purchaser:
                messages.error(request, "Unauthorized. You did not purchase this item.")
                return redirect(request.META.get('HTTP_REFERER', 'index'))

            # 2. Advanced Contract Matching Engine
            b2b_trade = None
            input_order = None

            # Attempt A: Modern Cryptographic Match
            if txn.security_token:
                if txn.security_token.startswith('ORDER-'):
                    order_id = txn.security_token.split('-')[1]
                    input_order = InputOrder.objects.filter(order_id=order_id).first()
                else:
                    b2b_trade = DirectTradeProposal.objects.filter(security_token=txn.security_token).first()
            
            # Attempt B: Legacy Match by Listing (If it hasn't been deleted)
            if not b2b_trade and not input_order and txn.item_purchased:
                b2b_trade = DirectTradeProposal.objects.filter(listing=txn.item_purchased, buyer=request.user).first()
                if not b2b_trade:
                    input_order = InputOrder.objects.filter(product=txn.item_purchased, farmer=request.user).first()

            # Attempt C: THE ULTIMATE FALLBACK (If the farmer deleted the listing!)
            # Just prove that these two users had a legitimate, completed contract together.
            if not b2b_trade and not input_order:
                b2b_trade = DirectTradeProposal.objects.filter(buyer=request.user, farmer=txn.vendor).first()

            # Final Security Gate
            if not b2b_trade and not input_order:
                messages.error(request, "System Error: The original contract was deleted by the vendor and cannot be verified.")
                return redirect(request.META.get('HTTP_REFERER', 'index'))

            # 3. Defensive Programming: Block Duplicate Reviews safely
            duplicate_exists = False
            if b2b_trade and UnifiedReview.objects.filter(b2b_trade=b2b_trade).exists():
                duplicate_exists = True
            elif input_order and UnifiedReview.objects.filter(input_order=input_order).exists():
                duplicate_exists = True

            if duplicate_exists:
                messages.warning(request, "You have already submitted a review for this transaction.")
                return redirect(request.META.get('HTTP_REFERER', 'index'))

            # 4. Save the Review to our Unified Table
            UnifiedReview.objects.create(
                reviewer=request.user,
                reviewee=txn.vendor,
                rating=int(rating),
                comment=comment,
                b2b_trade=b2b_trade,
                input_order=input_order
            )

            # 5. --- SEND BEAUTIFUL HTML EMAIL NOTIFICATION TO VENDOR ---
            try:
                vendor = txn.vendor
                subject = f"Kultiva Trust Engine: New {rating}-Star Review!"
                html_msg = f"""
                <div style="font-family: Arial; padding: 20px; border: 1px solid #e0d4c3; border-radius: 12px; max-width: 600px; background: #fdfbf7;">
                    <h2 style="color: #1e293b; border-bottom: 2px solid #fbc02d; padding-bottom: 10px;">New Vendor Assessment</h2>
                    <p style="font-size: 16px; color: #333;">Hello <strong>{vendor.username}</strong>,</p>
                    <p style="font-size: 15px; color: #555;"><strong>{request.user.username}</strong> has just submitted feedback for your recent transaction.</p>
                    
                    <div style="background: #ffffff; padding: 20px; border-left: 5px solid #fbc02d; margin: 20px 0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                        <h3 style="margin: 0; color: #f57f17; font-size: 20px;">Rating: {rating} / 5 Stars</h3>
                        <p style="font-style: italic; color: #666; font-size: 16px; margin-top: 10px;">"{comment if comment else 'No written comment provided.'}"</p>
                    </div>
                    
                    <p style="color: #555; font-size: 14px;">This review has been published to your public portfolio. Keep up the great work building trust in the Kultiva ecosystem!</p>
                </div>
                """
                # Send the email using Django's core mail engine
                from django.utils.html import strip_tags
                from django.core.mail import send_mail
                
                send_mail(
                    subject, 
                    strip_tags(html_msg), 
                    'admin@kultiva.com', 
                    [vendor.email], 
                    html_message=html_msg, 
                    fail_silently=True
                )
            except Exception as email_e:
                print(f"Failed to send review email: {email_e}")

            messages.success(request, f"Success! Your {rating}-star feedback for {txn.vendor.username} has been published.")

        except Exception as e:
            messages.error(request, f"Error processing feedback: {e}")

        # Seamlessly reload the page
        return redirect(request.META.get('HTTP_REFERER', 'buyer_purchase_history'))
        
    return redirect('index')

# --- BUYER: BUSINESS PROFILE & SECURE EMAIL ALERTS ---
@login_required
def buyer_profile(request):
    if request.user.role != User.Role.BUYER:
        return redirect('index')

    buyer_prof = get_object_or_404(BuyerProfile, user=request.user)
    address = request.user.addresses.first() # Get the first associated address

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Update Editable User Fields
                request.user.first_name = request.POST.get('first_name')
                request.user.last_name = request.POST.get('last_name')
                request.user.save()

                # 2. Update Editable Profile Fields
                buyer_prof.company_name = request.POST.get('company_name')
                buyer_prof.save()

                # 3. Update Shipping Address
                if address:
                    address.village = request.POST.get('village')
                    address.district = request.POST.get('district')
                    address.state = request.POST.get('state')
                    address.pincode = request.POST.get('pincode')
                    address.save()

                # --- SECURE EMAIL ENGINE ---
                # Mask sensitive data for email transmission (e.g. GSTIN: 22AAAAA0000A1Z5 -> *******0000A1Z5)
                masked_gst = f"********{buyer_prof.gst_number[-4:]}" if buyer_prof.gst_number else "Not Provided"
                masked_reg = f"********{buyer_prof.iec_code[-4:]}" if buyer_prof.iec_code else "Not Provided"
                
                # Beautiful Kultiva Branded HTML Email
                email_html = f"""
                <!DOCTYPE html>
                <html>
                <body style="background-color: #f4f7f6; font-family: 'Helvetica Neue', Arial, sans-serif; padding: 40px 0; margin: 0;">
                    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                        
                        <div style="background: linear-gradient(135deg, #0288d1, #01579b); padding: 30px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 32px; letter-spacing: 2px; text-transform: uppercase;">KULTIVA</h1>
                            <p style="color: #bbdefb; margin: 5px 0 0 0; font-size: 14px;">Enterprise Supply Chain Ecosystem</p>
                        </div>

                        <div style="padding: 40px 30px;">
                            <h2 style="color: #1e293b; font-size: 22px; margin-top: 0;">Profile Update Successful</h2>
                            <p style="color: #555; font-size: 16px; line-height: 1.6;">Hello <strong>{request.user.first_name}</strong>,</p>
                            <p style="color: #555; font-size: 16px; line-height: 1.6;">This is an automated notification confirming that changes were recently made to your Kultiva Buyer Profile. Below is a summary of your active business identity.</p>
                            
                            <div style="background: #f8f9fa; border-left: 4px solid #0288d1; padding: 20px; border-radius: 6px; margin: 25px 0;">
                                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                                    <tr><td style="padding: 8px 0; color: #888;">Company Name:</td><td style="text-align: right; color: #1e293b; font-weight: bold;">{buyer_prof.company_name}</td></tr>
                                    <tr><td style="padding: 8px 0; color: #888;">Account ID:</td><td style="text-align: right; color: #1e293b; font-weight: bold;">BUY-{request.user.pk}</td></tr>
                                    <tr><td style="padding: 8px 0; color: #888;">Shipping Hub:</td><td style="text-align: right; color: #1e293b; font-weight: bold;">{address.district}, {address.state}</td></tr>
                                    <tr><td colspan="2" style="border-bottom: 1px solid #ddd; padding-top: 10px;"></td></tr>
                                    <tr><td style="padding: 15px 0 8px 0; color: #888;">GST Number:</td><td style="padding-top: 15px; text-align: right; color: #1b5e20; font-weight: bold;">{masked_gst} <span style="font-size:10px; background:#e8f5e9; padding:2px 5px; border-radius:4px;">VERIFIED</span></td></tr>
                                    <tr><td style="padding: 8px 0; color: #888;">Company Reg:</td><td style="text-align: right; color: #1b5e20; font-weight: bold;">{masked_reg} <span style="font-size:10px; background:#e8f5e9; padding:2px 5px; border-radius:4px;">VERIFIED</span></td></tr>
                                </table>
                            </div>

                            <p style="color: #888; font-size: 13px; line-height: 1.5; margin-top: 30px;">
                                <i style="color: #d32f2f;">Security Notice:</i> If you did not authorize these changes, please contact the Kultiva Admin team immediately to secure your Escrow Vault.
                            </p>
                        </div>

                        <div style="background: #1e293b; text-align: center; padding: 20px; color: #94a3b8; font-size: 12px;">
                            &copy; 2026 Kultiva AI Agriculture Platform. All rights reserved.<br>
                            This is an automated security message. Do not reply.
                        </div>
                    </div>
                </body>
                </html>
                """

                # Send the Email
                send_mail(
                    subject="Kultiva Security: Business Profile Updated",
                    message=strip_tags(email_html), # Fallback for non-HTML email clients
                    from_email='admin@kultiva.com',
                    recipient_list=[request.user.email],
                    html_message=email_html,
                    fail_silently=True
                )

                messages.success(request, "Your business profile has been successfully updated. A confirmation email has been sent.")
                return redirect('buyer_profile')

        except Exception as e:
            messages.error(request, f"Failed to update profile: {str(e)}")
            return redirect('buyer_profile')

    # For GET requests
    context = {
        'profile': buyer_prof,
        'address': address
    }
    return render(request, 'buyer_profile.html', context)

# --- BUYER: LOGISTICS HANDSHAKE (SCHEDULE PICKUP) ---
@login_required
def schedule_pickup(request, proposal_id):
    if request.method == 'POST' and request.user.role == User.Role.BUYER:
        try:
            proposal = get_object_or_404(DirectTradeProposal, id=proposal_id, buyer=request.user)
            pickup_datetime_str = request.POST.get('pickup_datetime')
            
            if pickup_datetime_str:
                # Save the logistics date to the database
                proposal.scheduled_pickup_date = parse_datetime(pickup_datetime_str)
                proposal.save()
                
                # Format data for the email
                farmer_email = proposal.farmer.email
                farmer_name = proposal.farmer.first_name or proposal.farmer.username
                buyer_name = request.user.buyer_profile.company_name if hasattr(request.user, 'buyer_profile') else request.user.username
                crop_name = proposal.listing.title
                date_formatted = proposal.scheduled_pickup_date.strftime("%B %d, %Y at %I:%M %p")
                
                # --- THE STUNNING CSS LOGISTICS EMAIL ---
                email_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&display=swap');
                    body {{ font-family: 'Montserrat', sans-serif; background-color: #f4f7f6; margin: 0; padding: 40px; }}
                    .email-wrapper {{ max-width: 650px; margin: auto; background: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 15px 35px rgba(0,0,0,0.1); border: 1px solid #e0e0e0; }}
                    .header {{ background: linear-gradient(135deg, #1b5e20, #2e7d32); padding: 40px 30px; text-align: center; color: white; }}
                    .header h1 {{ margin: 0; font-size: 36px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase; }}
                    .header p {{ margin: 10px 0 0 0; font-size: 16px; opacity: 0.9; }}
                    .content {{ padding: 40px 30px; color: #333; }}
                    .content h2 {{ color: #1e293b; font-size: 24px; margin-top: 0; }}
                    .highlight-box {{ background: #e8f5e9; border-left: 5px solid #2e7d32; padding: 25px; border-radius: 10px; margin: 30px 0; text-align: center; }}
                    .highlight-box h3 {{ margin: 0 0 10px 0; color: #1b5e20; font-size: 18px; text-transform: uppercase; }}
                    .highlight-box .date {{ font-size: 28px; font-weight: 900; color: #2e7d32; margin: 0; }}
                    .details-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    .details-table td {{ padding: 12px 0; border-bottom: 1px solid #eee; font-size: 15px; }}
                    .details-table td:first-child {{ color: #888; font-weight: bold; width: 40%; }}
                    .details-table td:last-child {{ color: #1e293b; font-weight: 900; text-align: right; }}
                    .footer {{ background: #1e293b; color: #94a3b8; text-align: center; padding: 25px; font-size: 13px; }}
                </style>
                </head>
                <body>
                    <div class="email-wrapper">
                        <div class="header">
                            <h1>KULTIVA</h1>
                            <p>Logistics & Dispatch Alert</p>
                        </div>
                        <div class="content">
                            <h2>Pickup Scheduled! 🚛</h2>
                            <p style="font-size: 16px; line-height: 1.6;">Hello <strong>{farmer_name}</strong>,</p>
                            <p style="font-size: 16px; line-height: 1.6;">Great news! The buyer (<strong>{buyer_name}</strong>) has successfully locked the funds in the Escrow Vault and has officially scheduled their logistics team to pick up the harvest.</p>
                            
                            <div class="highlight-box">
                                <h3>Scheduled Arrival</h3>
                                <p class="date">{date_formatted}</p>
                            </div>
                            
                            <table class="details-table">
                                <tr><td>Contract Ref:</td><td>KUL-{proposal.id}</td></tr>
                                <tr><td>Commodity:</td><td>{crop_name}</td></tr>
                                <tr><td>Total Volume:</td><td>{proposal.listing.available_stock} {proposal.listing.unit_of_measure}</td></tr>
                            </table>
                            
                            <p style="font-size: 15px; color: #555; margin-top: 30px; line-height: 1.5; background: #fff8e1; padding: 15px; border-radius: 8px; border-left: 4px solid #fbc02d;">
                                <strong>Action Required:</strong> Please ensure the harvest is fully packed, weighed, and ready at the gate. Have your smartphone ready to display the Kultiva QR Code when the truck arrives so the escrow funds can be instantly released to your account.
                            </p>
                        </div>
                        <div class="footer">
                            &copy; 2026 Kultiva AI Supply Chain Platform.<br>
                            This is an automated dispatch alert. Do not reply.
                        </div>
                    </div>
                </body>
                </html>
                """
                
                # Send the Alert
                send_mail(
                    subject=f"Logistics Alert: Pickup Scheduled for {crop_name}",
                    message=strip_tags(email_html),
                    from_email='admin@kultiva.com',
                    recipient_list=[farmer_email],
                    html_message=email_html,
                    fail_silently=True
                )
                
                messages.success(request, "Pickup successfully scheduled! The farmer has been notified via email.")
        except Exception as e:
            messages.error(request, f"Error scheduling pickup: {str(e)}")
            
    return redirect('buyer_escrow_detail', proposal_id=proposal_id)

@login_required
def buyer_farmer_list(request):
    # 1. Strict Security Gate: Only Buyers allowed
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied. Only registered Buyers can view the Farmer Network.")
        return redirect('index')

    try:
        # 2. The Optimized Query (Grabs Active/Verified Farmers + their linked data in one shot)
        farmers = User.objects.filter(
            role=User.Role.FARMER,
            is_verified=True,
            is_active=True
        ).select_related(
            'farmer_profile', 
            'manual_soil_report'
        ).prefetch_related(
            'addresses', 
            'listings'
        ).order_by('-date_joined')

        # 3. Simple Search Engine Logic
        search_query = request.GET.get('q', '').strip()
        if search_query:
            farmers = farmers.filter(
                Q(username__icontains=search_query) |
                Q(addresses__district__icontains=search_query) |
                Q(farmer_profile__soil_type__icontains=search_query)
            ).distinct() # distinct() prevents duplicates if multiple addresses match

        context = {
            'farmers': farmers,
            'search_query': search_query
        }
        return render(request, 'buyer_farmer_list.html', context)
        
    except Exception as e:
        # Ultimate fallback to prevent 500 server errors
        messages.error(request, f"Error loading the network: {e}")
        return redirect('buyer_dashboard')

@login_required
def buyer_view_farmer_profile(request, farmer_id):
    # 1. Security Gate
    if request.user.role != User.Role.BUYER:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        # 2. Fetch the specific farmer securely (Must be verified)
        farmer = get_object_or_404(User, user_id=farmer_id, role=User.Role.FARMER, is_verified=True)
        
        # 3. Extract profile details safely
        address = farmer.addresses.first()
        profile = getattr(farmer, 'farmer_profile', None)
        soil_report = getattr(farmer, 'manual_soil_report', None)

        # 4. Fetch only their ACTIVE farm produce
        active_listings = MarketplaceListing.objects.filter(
            listed_by=farmer, 
            status='ACTIVE', 
            wing='PRODUCE'
        ).order_by('-created_at')

        context = {
            'farmer': farmer,
            'address': address,
            'profile': profile,
            'soil_report': soil_report,
            'listings': active_listings
        }
        return render(request, 'buyer_view_farmer_profile.html', context)
        
    except Exception as e:
        messages.error(request, "Could not load the farmer's portfolio.")
        return redirect('buyer_farmer_list')

@login_required
def seller_dashboard(request):
    # 1. Security Check
    if request.user.role != User.Role.SELLER:
        messages.error(request, "Access Denied. Vendor Portal Only.")
        return redirect('index')

    try:
        # 2. Base Queries
        seller_products = MarketplaceListing.objects.filter(listed_by=request.user)
        active_orders = InputOrder.objects.filter(product__listed_by=request.user).exclude(status='CANCELLED')

        # 3. Top-Level KPIs
        total_revenue = active_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        orders_count = active_orders.count()
        
        # 4. Low Stock Alerts (Stock < 10)
        low_stock_items = seller_products.filter(available_stock__lt=10).order_by('available_stock')[:5]
        
        # 5. Top Selling Products (Calculated by total quantity sold)
        top_products = seller_products.annotate(
            total_sold=Sum('inputorder__quantity')
        ).filter(total_sold__isnull=False).order_by('-total_sold')[:5]

        # 6. Algorithmic Chart Data (Last 6 Months Revenue)
        chart_labels = []
        chart_data = []
        now = timezone.now()
        
        # Loop backwards 6 months to build the X and Y axes
        for i in range(5, -1, -1):
            target_date = now - datetime.timedelta(days=30*i)
            month_name = calendar.month_abbr[target_date.month]
            chart_labels.append(month_name)
            
            month_rev = active_orders.filter(
                created_at__year=target_date.year,
                created_at__month=target_date.month
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            
            chart_data.append(float(month_rev))

        context = {
            'total_revenue': total_revenue,
            'orders_count': orders_count,
            'low_stock_items': low_stock_items,
            'top_products': top_products,
            'chart_labels': chart_labels,
            'chart_data': chart_data,
        }
        return render(request, 'seller_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Dashboard Analytics Error: {e}")
        return redirect('index')

@login_required
def seller_reports(request):
    if request.user.role != User.Role.SELLER:
        messages.error(request, "Access Denied. Vendor portal only.")
        return redirect('index')

    try:
        # 1. Base Query
        all_orders = InputOrder.objects.filter(product__listed_by=request.user).order_by('-created_at')
        
        # 2. Time Filter Logic
        time_filter = request.GET.get('time_filter', 'all')
        now = timezone.now()
        
        if time_filter == 'week':
            start_of_week = now - datetime.timedelta(days=7)
            all_orders = all_orders.filter(created_at__gte=start_of_week)
        elif time_filter == 'month':
            all_orders = all_orders.filter(created_at__year=now.year, created_at__month=now.month)
        elif time_filter == 'year':
            all_orders = all_orders.filter(created_at__year=now.year)
            
        # 3. Financials only count non-cancelled, successfully paid orders
        valid_orders = all_orders.exclude(status='CANCELLED')
        
        # Total Gross Sales (Money collected from farmers)
        total_gross_sales = valid_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        
        # Approximate GST Calculations (15% blended rate for UI demo)
        tax_multiplier = Decimal('1.15')
        net_earnings = total_gross_sales / tax_multiplier
        gst_collected = total_gross_sales - net_earnings

        context = {
            'total_sales': round(total_gross_sales, 2),
            'net_earnings': round(net_earnings, 2),
            'gst_collected': round(gst_collected, 2),
            'recent_transactions': all_orders[:50], # Expanded ledger to 50 for better filtering view
            'time_filter': time_filter, # Pass back to UI to keep dropdown selected
        }
        return render(request, 'seller_reports.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading financial reports: {e}")
        return redirect('seller_dashboard')

@login_required
def seller_receipt_detail(request, order_id):
    """A pure, read-only financial receipt view for accounting purposes."""
    if request.user.role != User.Role.SELLER:
        messages.error(request, "Access Denied. Vendor portal only.")
        return redirect('index')

    try:
        # Fetch the order securely
        order = get_object_or_404(InputOrder, order_id=order_id, product__listed_by=request.user)
        
        # Pure Financial Breakdown
        packaging_fee = Decimal('20.00')
        subtotal_inclusive = order.total_amount - packaging_fee
        
        # Calculate exact GST rate based on product category
        gst_rate = 5 if order.product.category in ['SEEDS', 'FERTILIZERS'] else 18
        tax_multiplier = Decimal(str(1 + (gst_rate / 100)))
        
        taxable_value = subtotal_inclusive / tax_multiplier
        total_gst = subtotal_inclusive - taxable_value

        context = {
            'order': order,
            'subtotal': round(taxable_value, 2),
            'gst': round(total_gst, 2),
            'gst_rate': gst_rate,
            'packaging_fee': packaging_fee,
        }
        return render(request, 'seller_receipt_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Could not load receipt: {e}")
        return redirect('seller_reports')
    
def register(request, role_type):
    """
    Handles the 'Register as Farmer' or 'Register as Buyer' links.
    """
    if role_type == 'farmer':
        # Renders the farmer registration page
        return render(request, 'farmerregister.html')
    elif role_type == 'buyer':
        # Placeholder for buyer registration
        return render(request, 'buyerregister.html', {'role_type': 'Buyer'})
    elif role_type == 'seller':
        # Placeholder for seller registration
        return render(request, 'sellerregister.html', {'role_type': 'Seller'})
    elif role_type == 'admin':
        # Placeholder for admin registration (if needed)
        return render(request, 'admin_dashboard.html', {'role_type': 'Admin'})
    
    # If the role doesn't match, send them back to login
    return redirect('login')

def check_email_availability(request):
    """
    AJAX view to check if email exists or is banned.
    """
    email = request.GET.get('email', None)
    response = {
        'is_taken': False,
        'error_message': ""
    }

    if email:
        # Check if ANY user exists with this email (Active or Inactive)
        user = User.objects.filter(email__iexact=email).first()

        if user:
            response['is_taken'] = True
            
            if user.is_active:
                # Case 1: Account exists and is active
                response['error_message'] = "This email is already registered. Please login."
            else:
                # Case 2: Account exists but was removed (Banned/Inactive)
                response['error_message'] = "This email is associated with a restricted/removed account."

    return JsonResponse(response)

def check_email_availability(request):
    """
    AJAX view to check if email exists or is banned.
    """
    email = request.GET.get('email', None)
    response = {
        'is_taken': False,
        'error_message': ""
    }

    if email:
        # Check if ANY user exists with this email (Active or Inactive)
        user = User.objects.filter(email__iexact=email).first()

        if user:
            response['is_taken'] = True
            
            if user.is_active:
                # Case 1: Account exists and is active
                response['error_message'] = "This email is already registered. Please login."
            else:
                # Case 2: Account exists but was removed (Banned/Inactive)
                response['error_message'] = "This email is associated with a restricted/removed account."

    return JsonResponse(response)

# ==========================================
# NEW: REAL-TIME AADHAR VALIDATION ENGINE
# ==========================================
def check_aadhar_availability(request):
    """
    AJAX view to check if an Aadhar number is already registered to another farmer.
    Prevents duplicate accounts in real-time before form submission.
    """
    aadhar = request.GET.get('aadhar', None)
    
    response = {
        'is_taken': False,
        'error_message': ""
    }

    if aadhar:
        # Clean the input just in case
        aadhar = str(aadhar).strip()
        
        # Check if this Aadhar already exists in the FarmerProfile table
        # We use .exists() because it is highly optimized for database performance
        is_registered = FarmerProfile.objects.filter(aadhar_no=aadhar).exists()

        if is_registered:
            response['is_taken'] = True
            response['error_message'] = "This Aadhar number is already registered in our system."

    return JsonResponse(response)

# ==========================================
# NEW: REAL-TIME GST VALIDATION ENGINE
# ==========================================
def check_gst_availability(request):
    """
    AJAX view to check if a GST number is already registered to another corporate buyer.
    Prevents duplicate corporate accounts in real-time.
    """
    gst = request.GET.get('gst', None)
    
    response = {
        'is_taken': False,
        'error_message': ""
    }

    if gst:
        # Clean the input to uppercase to match Indian GST format
        gst = str(gst).strip().upper()
        
        # Check if this GST already exists in the BuyerProfile table
        is_registered = BuyerProfile.objects.filter(gst_number=gst).exists()

        if is_registered:
            response['is_taken'] = True
            response['error_message'] = "This GST Number is already registered in our system."

    return JsonResponse(response)

# ==========================================
# NEW: REAL-TIME SELLER VALIDATION ENGINES
# ==========================================
def check_shopname_availability(request):
    shop_name = request.GET.get('shop_name', None)
    response = {'is_taken': False, 'error_message': ""}

    if shop_name:
        shop_name = str(shop_name).strip()
        if SellerProfile.objects.filter(shop_name__iexact=shop_name).exists():
            response['is_taken'] = True
            response['error_message'] = "This Shop Name is already registered on Kultiva."
            
    return JsonResponse(response)

def check_license_availability(request):
    license_number = request.GET.get('license_number', None)
    response = {'is_taken': False, 'error_message': ""}

    if license_number:
        license_number = str(license_number).strip().upper()
        if SellerProfile.objects.filter(license_number=license_number).exists():
            response['is_taken'] = True
            response['error_message'] = "This License Number is already registered."
            
    return JsonResponse(response)

# ==========================================
# NEW: REAL-TIME LOGIN EMAIL CHECKER
# ==========================================
def check_login_email(request):
    """
    AJAX view to check if an email exists during login, 
    and return its specific status (Active, Pending, Suspended, Not Found).
    """
    email = request.GET.get('email', None)
    
    response = {
        'status': 'not_found',
        'message': "No account found with this email."
    }

    if email:
        email = str(email).strip()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            if user.is_active and user.is_verified:
                response['status'] = 'active'
                response['message'] = "Account verified. Please enter your password."
            elif user.is_active and not user.is_verified:
                response['status'] = 'pending'
                response['message'] = "Account exists but is pending Admin approval."
            elif not user.is_active:
                response['status'] = 'banned'
                response['message'] = "This account has been suspended or removed by Admin."

    return JsonResponse(response)

from django.http import JsonResponse
from .models import BuyerProfile 

def check_apeda_availability(request):
    """
    API endpoint for real-time frontend validation of APEDA RCMC numbers.
    Checks if a Corporate Buyer has already registered with this number.
    """
    apeda = request.GET.get('apeda', None)
    data = {
        'is_taken': False,
        'error_message': ''
    }
    
    if apeda:
        # NOTE: Replace 'apeda_org' below with the exact field name you used 
        # in your BuyerProfile model (e.g., apeda_number, apeda_rcmc, etc.)
        if BuyerProfile.objects.filter(apeda_org=apeda).exists():
            data['is_taken'] = True
            data['error_message'] = 'This APEDA number is already registered with another account.'
            
    return JsonResponse(data)

# ==========================================
# SECURE PASSWORD RECOVERY PIPELINE
# ==========================================
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, "Please enter your registered email address.")
            return redirect('forgot_password')

        user = User.objects.filter(email__iexact=email).first()
        
        if user:
            otp = str(random.randint(100000, 999999))
            
            # Store OTP, Email, and a STRICT 60-SECOND EXPIRY timestamp in session
            request.session['reset_otp'] = otp
            request.session['reset_email'] = email
            request.session['otp_expiry'] = time.time() + 60  
            request.session['otp_verified'] = False # Reset verification state
            
            subject = "Kultiva Security - Password Reset OTP"
            message = f"""
            Hello {user.username},
            
            Your Secure One-Time Password (OTP) is: {otp}
            
            This code will expire in exactly 60 seconds.
            If you did not request a password reset, please ignore this email.
            
            Regards,
            Kultiva Security Team
            """
            
            try:
                send_mail(subject, message, 'admin@kultiva.com', [email], fail_silently=False)
                return redirect('verify_otp')
            except Exception as e:
                logger.error(f"Failed to send OTP to {email}: {e}")
                messages.error(request, "System error: Unable to send email.")
                return redirect('forgot_password')
        else:
            messages.error(request, "No active account found with that email address.")
            return redirect('forgot_password')

    return render(request, 'forgot_password.html')


def verify_otp(request):
    # Security Gate
    if 'reset_email' not in request.session or 'reset_otp' not in request.session:
        messages.error(request, "Session expired. Please request a new OTP.")
        return redirect('forgot_password')
        
    # Calculate exactly how much time is left for the frontend JS to use
    expiry = request.session.get('otp_expiry', 0)
    time_left = max(0, int(expiry - time.time()))

    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        
        # 1. Check Expiry
        if time.time() > expiry:
            messages.error(request, "OTP has expired. Please request a new one.")
            return redirect('forgot_password')

        # 2. Check Match
        if entered_otp != request.session['reset_otp']:
            messages.error(request, "Invalid OTP. Please check the code and try again.")
            return render(request, 'verify_otp.html', {'time_left': time_left})
            
        # 3. Success! Unlock the next phase
        request.session['otp_verified'] = True
        messages.success(request, "OTP Verified Successfully! You may now set a new password.")
        return redirect('set_new_password')

    return render(request, 'verify_otp.html', {'time_left': time_left})


def set_new_password(request):
    # Strict Security Gate: They MUST have verified the OTP to access this page
    if not request.session.get('otp_verified'):
        messages.error(request, "Unauthorized access. Please verify your OTP first.")
        return redirect('forgot_password')

    email = request.session.get('reset_email')

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'set_new_password.html')
            
        pass_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
        if not re.match(pass_regex, new_password):
            messages.error(request, "Password does not meet security requirements.")
            return render(request, 'set_new_password.html')

        try:
            with transaction.atomic():
                user = User.objects.get(email__iexact=email)
                user.set_password(new_password)
                user.save()
                
                # Cleanup Session completely to prevent re-use
                for key in ['reset_otp', 'reset_email', 'otp_expiry', 'otp_verified']:
                    if key in request.session:
                        del request.session[key]
                
                messages.success(request, "Your password has been successfully reset. You may now log in.")
                return redirect('login')
                
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            messages.error(request, "System error occurred. Please try again.")
            return render(request, 'set_new_password.html')

    return render(request, 'set_new_password.html')

def seller_terms(request):
    return render(request, 'sellerterms.html')

def farmer_terms(request):
    return render(request, 'farmer_terms.html')

def buyer_terms(request):
    return render(request, 'buyer_terms.html')

# --- SELLER: ADD INVENTORY LISTING ---
@login_required
def add_seller_listing(request):
    # Strict Role-Based Access Control
    if request.user.role != User.Role.SELLER:
        messages.error(request, "Access Denied. Only registered Sellers can access this portal.")
        return redirect('index')

    if request.method == 'POST':
        try:
            # 1. Capture Standard B2B Fields
            category = request.POST.get('category')
            title = request.POST.get('title')
            brand = request.POST.get('variety_or_brand')
            price = request.POST.get('price')
            unit = request.POST.get('unit_of_measure')
            stock = request.POST.get('available_stock')
            min_order = request.POST.get('min_order_quantity', 1)
            description = request.POST.get('description')
            image = request.FILES.get('image')

            # 2. Pack Dynamic "Magic Field" Data (The JSON Specs)
            specs = {}
            if category == 'SEEDS':
                specs['germination_rate'] = request.POST.get('spec_germination', '')
                specs['treatment'] = request.POST.get('spec_treatment', '')
            elif category == 'FERTILIZERS' or category == 'AGROCHEMICALS':
                specs['npk_ratio'] = request.POST.get('spec_npk', '')
                specs['expiry_date'] = request.POST.get('spec_expiry', '')
            elif category == 'TOOLS' or category == 'MACHINERY':
                specs['power_rating'] = request.POST.get('spec_power', '')
                specs['warranty_months'] = request.POST.get('spec_warranty', '')

            # 3. Save to the Unified Database
            listing = MarketplaceListing.objects.create(
                listed_by=request.user,
                wing='INPUT',  # Hard-locked for Sellers
                category=category,
                title=title,
                variety_or_brand=brand,
                price=price,
                unit_of_measure=unit,
                available_stock=stock,
                min_order_quantity=min_order,
                description=description,
                image=image,
                specifications=specs,
                status='ACTIVE'
            )

            # 4. Send Instant Confirmation Email
            seller_html = f"""
            <div style="font-family: Arial; padding: 20px; border: 1px solid #0288d1; border-radius: 10px;">
                <h2 style="color: #01579b;">Inventory Published</h2>
                <p>Hello {request.user.username},</p>
                <p>Your product <strong>{title}</strong> is now live on the Kultiva Input Marketplace.</p>
                <div style="background: #e1f5fe; padding: 15px; border-left: 4px solid #0288d1;">
                    <p><strong>Stock:</strong> {stock} {unit}</p>
                    <p><strong>Price:</strong> ₹{price} / {unit}</p>
                </div>
                <p>Farmers can now purchase this directly from their dashboards.</p>
            </div>
            """
            send_mail(
                f"Kultiva: Listing Active - {title}", strip_tags(seller_html), 
                'admin@kultiva.com', [request.user.email], 
                html_message=seller_html, fail_silently=True
            )

            messages.success(request, f"Success! '{title}' is now live on the vendor marketplace.")
            # Redirect to their dashboard or inventory manager
            return redirect('add_seller_listing') 

        except Exception as e:
            messages.error(request, f"Error creating listing: {e}")
            return redirect('add_seller_listing')

    # If GET request, show the form
    return render(request, 'seller_add_item.html')

# --- SELLER PROFILE MANAGEMENT ---
@login_required
def seller_profile_view(request):
    if request.user.role != User.Role.SELLER:
        return redirect('index')

    address = request.user.addresses.first()
    
    # THE FIX: Use get_or_create to ensure the profile ALWAYS exists!
    profile, created = SellerProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # 1. Update Allowed User & Profile Fields
        new_username = request.POST.get('username')
        if new_username:
            request.user.username = new_username
            request.user.save()
            
        new_shop_name = request.POST.get('shop_name')
        if new_shop_name:
            profile.shop_name = new_shop_name
            profile.save() # This will now successfully save every time!

        # 2. Update Allowed Address Fields
        if address:
            address.village = request.POST.get('village')
            address.district = request.POST.get('district')
            # ... (The rest of your address and GPS logic remains exactly the same)
            address.state = request.POST.get('state')
            address.pincode = request.POST.get('pincode')
            
            # --- RANDOM GPS GENERATOR ---
            # We generate random floats to keep the database happy without bothering the vendor.
            # Ranges roughly cover the Indian subcontinent.
            address.latitude = round(random.uniform(8.4, 37.6), 6)
            address.longitude = round(random.uniform(68.7, 97.25), 6)
            
            address.save()

        # 3. Send Success Notification Email
        email_html = f"""
        <div style="font-family: Arial; padding: 20px; border: 1px solid #0288d1; border-radius: 10px;">
            <h2 style="color: #01579b;">Profile Updated</h2>
            <p>Hello {request.user.username},</p>
            <p>Your Kultiva Vendor Profile has been successfully updated.</p>
            <div style="background: #e1f5fe; padding: 15px; border-left: 4px solid #0288d1;">
                <p><strong>Store Name:</strong> {profile.shop_name if profile else 'N/A'}</p>
                <p><strong>Location:</strong> {address.district if address else 'N/A'}, {address.state if address else 'N/A'}</p>
            </div>
            <p>If you did not make these changes, please contact our support team immediately.</p>
        </div>
        """
        send_mail(
            "Kultiva: Vendor Profile Updated", 
            strip_tags(email_html), 
            'admin@kultiva.com', 
            [request.user.email], 
            html_message=email_html, 
            fail_silently=True
        )

        messages.success(request, "Profile updated successfully! A confirmation email has been sent.")
        return redirect('seller_profile')

    # Security: Mask the Business Registration Number for display
    masked_reg_no = "N/A"
    if profile and profile.license_number:
        if len(profile.license_number) >= 4:
            masked_reg_no = "********" + profile.license_number[-4:]
        else:
            masked_reg_no = "****"

    context = {
        'address': address,
        'profile': profile,
        'masked_reg_no': masked_reg_no
    }
    
    return render(request, 'seller_profile.html', context)

@login_required
def seller_orders(request):
    # 1. Security Check
    if request.user.role != User.Role.SELLER:
        messages.error(request, "Access Denied. Seller portal only.")
        return redirect('index')

    try:
        # 2. Base Query: Only fetch orders where the product was listed by THIS seller
        orders = InputOrder.objects.filter(
            product__listed_by=request.user
        ).select_related('farmer', 'product').order_by('-created_at')

        # 3. Calculate Enterprise KPIs
        total_orders = orders.count()
        pending_orders = orders.filter(status='PENDING').count()
        delivered_orders = orders.filter(status='DELIVERED')
        delivered_count = delivered_orders.count()
        
        # Calculate Total Revenue (Only for delivered items)
        total_revenue = delivered_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

        # 4. Search and Filters
        query = request.GET.get('q', '').strip()
        if query:
            orders = orders.filter(
                Q(order_id__icontains=query) |
                Q(farmer__username__icontains=query) |
                Q(product__title__icontains=query)
            )

        status_filter = request.GET.get('status', '')
        if status_filter:
            orders = orders.filter(status=status_filter.upper())

        # 5. Pagination (10 orders per page)
        paginator = Paginator(orders, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'orders': page_obj,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'delivered_count': delivered_count,
            'total_revenue': total_revenue,
            'search_query': query,
            'current_status': status_filter,
        }
        return render(request, 'seller_orders.html', context)

    except Exception as e:
        messages.error(request, f"Error loading dashboard: {e}")
        return redirect('index')

from django.utils import timezone
import datetime

@login_required
def seller_orders(request):
    if request.user.role != User.Role.SELLER:
        messages.error(request, "Access Denied. Seller portal only.")
        return redirect('index')

    try:
        # Base Query
        orders = InputOrder.objects.filter(
            product__listed_by=request.user
        ).select_related('farmer', 'product').order_by('-created_at')

        # Base KPIs
        total_orders = orders.count()
        pending_orders = orders.filter(status='PENDING').count()
        delivered_count = orders.filter(status='DELIVERED').count()
        
        # --- NEW: Direct E-Commerce Revenue Logic ---
        # Revenue is recognized immediately upon purchase (excluding cancelled)
        rev_filter = request.GET.get('rev_filter', 'all')
        now = timezone.now()
        
        active_orders = orders.exclude(status='CANCELLED')
        
        if rev_filter == 'month':
            revenue_qs = active_orders.filter(created_at__year=now.year, created_at__month=now.month)
        elif rev_filter == 'year':
            revenue_qs = active_orders.filter(created_at__year=now.year)
        else:
            revenue_qs = active_orders
            
        total_revenue = revenue_qs.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

        # Table Filters (Search & Status)
        query = request.GET.get('q', '').strip()
        if query:
            orders = orders.filter(
                Q(order_id__icontains=query) |
                Q(farmer__username__icontains=query) |
                Q(product__title__icontains=query)
            )

        status_filter = request.GET.get('status', '')
        if status_filter:
            orders = orders.filter(status=status_filter.upper())

        # Pagination
        paginator = Paginator(orders, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'orders': page_obj,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'delivered_count': delivered_count,
            'total_revenue': total_revenue,
            'search_query': query,
            'current_status': status_filter,
            'rev_filter': rev_filter,
        }
        return render(request, 'seller_orders.html', context)

    except Exception as e:
        messages.error(request, f"Error loading dashboard: {e}")
        return redirect('index')

@login_required
def seller_order_detail(request, order_id):
    if request.user.role != User.Role.SELLER:
        return redirect('index')

    try:
        # Fetch the order ensuring it belongs to this seller
        order = get_object_or_404(InputOrder, order_id=order_id, product__listed_by=request.user)
        
        # Calculate Invoice breakdown
        packaging_fee = Decimal('20.00')
        subtotal_inclusive = order.total_amount - packaging_fee
        
        # Approximate 5% or 18% GST reverse calculation
        gst_rate = 5 if order.product.category in ['SEEDS', 'FERTILIZERS'] else 18
        tax_multiplier = Decimal(str(1 + (gst_rate / 100)))
        taxable_value = subtotal_inclusive / tax_multiplier
        total_gst = subtotal_inclusive - taxable_value

        context = {
            'order': order,
            'subtotal': round(taxable_value, 2),
            'gst': round(total_gst, 2),
            'packaging_fee': packaging_fee,
        }
        return render(request, 'seller_order_detail.html', context)
    except Exception as e:
        messages.error(request, f"Could not load order details: {e}")
        return redirect('seller_orders')

@login_required
def update_order_status(request, order_id):
    """Updates status and sends ephemeral tracking data via email without saving to DB."""
    if request.method == 'POST' and request.user.role == User.Role.SELLER:
        order = get_object_or_404(InputOrder, order_id=order_id, product__listed_by=request.user)
        
        # Security: Prevent seller from modifying an already shipped/delivered order
        if order.status in ['SHIPPED', 'DELIVERED', 'CANCELLED']:
            messages.error(request, "This order is locked and cannot be modified.")
            return redirect('seller_order_detail', order_id=order_id)
            
        new_status = request.POST.get('new_status')
        notify_customer = request.POST.get('notify_customer') == 'on'
        
        # Sellers can only transition to SHIPPED or CANCELLED
        if new_status in ['SHIPPED', 'CANCELLED']:
            order.status = new_status
            order.save()
            
            # --- ENTERPRISE EMAIL NOTIFICATION (Ephemeral Tracking) ---
            if notify_customer:
                tracking_html = ""
                if new_status == 'SHIPPED':
                    status_msg = "has been dispatched and handed over to our logistics partner"
                    
                    courier = request.POST.get('courier_partner')
                    awb = request.POST.get('tracking_number')
                    url = request.POST.get('tracking_url')
                    
                    if awb and courier:
                        tracking_html = f"<p><strong>Courier:</strong> {courier.title()}<br><strong>Tracking Number (AWB):</strong> {awb}</p>"
                        if url:
                            tracking_html += f"<br><p><a href='{url}' style='background:#1b5e20; color:white; padding:10px 20px; text-decoration:none; border-radius:5px; font-weight:bold;'>Track Your Package</a></p>"
                else:
                    status_msg = "has been Cancelled"

                email_body = f"""
                <div style="font-family: Arial; padding: 20px; border: 1px solid #c5e1a5; border-radius: 10px; max-width: 600px;">
                    <h2 style="color: #1b5e20; border-bottom: 2px solid #fbc02d; padding-bottom: 10px;">Order Update: {order.order_id}</h2>
                    <p style="font-size: 16px;">Hello {order.farmer.username},</p>
                    <p style="font-size: 16px;">Your order for <strong>{order.product.title}</strong> {status_msg}.</p>
                    
                    <div style="background: #f1f8e9; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        {tracking_html}
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">Thank you for using the Kultiva Marketplace.</p>
                </div>
                """
                send_mail(f"Order {new_status.title()}: {order.order_id}", strip_tags(email_body), 'orders@kultiva.com', [order.farmer.email], html_message=email_body, fail_silently=True)
                
            messages.success(request, f"Order {order.order_id} successfully marked as {new_status}. Customer notified.")
        else:
            messages.error(request, "Invalid status transition.")
            
    return redirect('seller_order_detail', order_id=order_id)

@login_required
def export_seller_orders_csv(request):
    """Generates a downloadable CSV of the seller's orders for AI trend analysis."""
    if request.user.role != User.Role.SELLER:
        return HttpResponse("Unauthorized", status=401)
    
    # 1. Fetch the seller's orders
    orders = InputOrder.objects.filter(product__listed_by=request.user).order_by('-created_at')
    
    # 2. Respect the active filters (so if they filter by "Delivered", the CSV only shows Delivered)
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter.upper())
        
    query = request.GET.get('q', '').strip()
    if query:
        orders = orders.filter(
            Q(order_id__icontains=query) |
            Q(farmer__username__icontains=query) |
            Q(product__title__icontains=query)
        )

    # 3. Create the HttpResponse object with the appropriate CSV headers
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="kultiva_financial_trends.csv"'

    # 4. Write the Data
    writer = csv.writer(response)
    
    # Write the Header Row
    writer.writerow([
        'Order ID', 
        'Date Placed', 
        'Farmer (Buyer)', 
        'Product Category',
        'Product Title', 
        'Quantity Sold', 
        'Total Revenue (INR)', 
        'Fulfillment Status'
    ])

    # Loop through the database and write the rows
    for order in orders:
        writer.writerow([
            order.order_id,
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            order.farmer.username,
            order.product.get_category_display(),
            order.product.title,
            order.quantity,
            order.total_amount,
            order.get_status_display()
        ])

    return response


import re
from django.utils.html import strip_tags
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

def addfarmer(request):
    if request.method == 'POST':
        # 1. Collect & Sanitize User Data (Prevent XSS)
        name = strip_tags(request.POST.get('name', '')).strip()
        email = strip_tags(request.POST.get('email', '')).strip()
        password = request.POST.get('password', '')
        
        # 2. Collect & Sanitize Address Data
        village = strip_tags(request.POST.get('village', '')).strip()
        district = strip_tags(request.POST.get('district', '')).strip()
        state = strip_tags(request.POST.get('state', '')).strip()
        pincode = strip_tags(request.POST.get('pincode', '')).strip()
        latitude = request.POST.get('latitude', 0.0)  
        longitude = request.POST.get('longitude', 0.0)

        # 3. Collect & Sanitize Profile Data
        adhar = strip_tags(request.POST.get('adhar', '')).strip()
        land_area_str = request.POST.get('land_area', '0')
        soil_type = strip_tags(request.POST.get('soil_type', '')).strip()
        irrigation = strip_tags(request.POST.get('irrigation', '')).strip()

        # ==========================================
        # HARD BACKEND VALIDATION ENGINE
        # ==========================================
        
        # A. Name Validation (Min 3 chars, letters/spaces only)
        if len(name) < 3 or not re.match(r"^[A-Za-z\s]+$", name):
            messages.error(request, "Name must be at least 3 characters and contain only letters.")
            return render(request, 'farmerregister.html')

        # B. Email Validation (Format & Uniqueness check fallback)
        try:
            validate_email(email)
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "This email is already registered.")
                return render(request, 'farmerregister.html')
        except ValidationError:
            messages.error(request, "Invalid email format.")
            return render(request, 'farmerregister.html')

        # C. Password Validation (Min 8, Upper, Lower, Number, Special)
        pass_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
        if not re.match(pass_regex, password):
            messages.error(request, "Password must be at least 8 characters long and include an uppercase letter, lowercase letter, number, and special character.")
            return render(request, 'farmerregister.html')

        # D. Address Validation
        if len(village) < 2 or not re.match(r"^[A-Za-z\s]+$", village):
            messages.error(request, "Village must contain only letters and be at least 2 characters long.")
            return render(request, 'farmerregister.html')
            
        if not re.match(r"^\d{6}$", pincode):
            messages.error(request, "Pincode must be exactly 6 digits.")
            return render(request, 'farmerregister.html')

        # E. Farmer Profile Validation (Aadhar & Land)
        if not re.match(r"^\d{12}$", adhar):
            messages.error(request, "Aadhar must be exactly 12 digits.")
            return render(request, 'farmerregister.html')
            
        if FarmerProfile.objects.filter(aadhar_no=adhar).exists():
            messages.error(request, "This Aadhar number is already registered in the system.")
            return render(request, 'farmerregister.html')

        try:
            land_area = float(land_area_str)
            if land_area <= 0 or land_area > 1000: # Realistic bounds check
                raise ValueError
        except ValueError:
            messages.error(request, "Land area must be a valid positive number representing realistic hectares/acres.")
            return render(request, 'farmerregister.html')

        # ==========================================
        # DATABASE TRANSACTION
        # ==========================================
        try:
            with transaction.atomic():
                # Step A: Create User (EXPLICITLY set as unverified to enforce Admin Approval)
                user = User.objects.create_user(
                    username=name,
                    email=email,
                    password=password,
                    role=User.Role.FARMER,
                    is_verified=False # Critical for your approval workflow requirement
                )

                # Step B: Create Address
                Address.objects.create(
                    user=user, village=village, district=district,
                    state=state, pincode=pincode,
                    latitude=float(latitude), longitude=float(longitude)
                )

                # Step C: Create Farmer Profile
                FarmerProfile.objects.create(
                    user=user, aadhar_no=adhar, land_area=land_area,
                    soil_type=soil_type, irrigation=irrigation
                )
                
                # Step D: Send Welcome Email
                subject = "Kultiva - Registration Received"
                message = f"""
                Hello {name},

                Thank you for registering with Kultiva!
                
                Your account is currently under review by our Admin team. 
                You will receive another email once your verification is complete and you can log in.

                Regards,
                Team Kultiva
                """
                send_mail(subject, message, 'admin@kultiva.com', [email], fail_silently=False)
                
                return render(request, 'registration_success.html')

        except Exception as e:
            # Catch DB-level failures
            logger.error(f"Error registering farmer: {e}")
            messages.error(request, 'An unexpected system error occurred during registration. Please try again.')
            return render(request, 'farmerregister.html')

    return render(request, 'farmerregister.html')

def addbuyer(request):
    if request.method == 'POST':
        # 1. Collect & Sanitize User Data
        name = strip_tags(request.POST.get('name', '')).strip()
        email = strip_tags(request.POST.get('email', '')).strip()
        password = request.POST.get('password', '')
        
        # 2. Collect & Sanitize Address Data
        village = strip_tags(request.POST.get('village', '')).strip()
        district = strip_tags(request.POST.get('district', '')).strip()
        state = strip_tags(request.POST.get('state', '')).strip()
        pincode = strip_tags(request.POST.get('pincode', '')).strip()
        
        # 3. Collect & Sanitize Corporate Profile Data
        company_name = strip_tags(request.POST.get('company_name', '')).strip()
        gst_number = strip_tags(request.POST.get('gst_number', '')).strip().upper()
        iec_code = strip_tags(request.POST.get('iec_code', '')).strip().upper()
        apeda_org = strip_tags(request.POST.get('apeda_org', '')).strip()
        
        # ==========================================
        # HARD BACKEND VALIDATION ENGINE
        # ==========================================
        
        # A. Username & Email Validation
        if len(name) < 3 or not re.match(r"^[A-Za-z\s]+$", name):
            messages.error(request, "Username must be at least 3 characters and contain only letters.")
            return render(request, 'buyerregister.html')

        try:
            validate_email(email)
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "This email is already registered.")
                return render(request, 'buyerregister.html')
        except ValidationError:
            messages.error(request, "Invalid email format.")
            return render(request, 'buyerregister.html')

        # B. Password Validation (Corporate Security)
        pass_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
        if not re.match(pass_regex, password):
            messages.error(request, "Password must be at least 8 characters long and include an uppercase letter, lowercase letter, number, and special character.")
            return render(request, 'buyerregister.html')

        # C. Corporate Credentials Validation
        if len(company_name) < 2 or not re.match(r"^[A-Za-z0-9\s.,&'-]+$", company_name):
            messages.error(request, "Invalid Company Name format.")
            return render(request, 'buyerregister.html')

        # GST format: 15 alphanumeric characters strictly enforced
        if not re.match(r"^[A-Z0-9]{15}$", gst_number):
            messages.error(request, "GST Number must be exactly 15 alphanumeric characters.")
            return render(request, 'buyerregister.html')
            
        if BuyerProfile.objects.filter(gst_number=gst_number).exists():
            messages.error(request, "This GST Number is already registered to another company.")
            return render(request, 'buyerregister.html')

        if not re.match(r"^[A-Z0-9]{10}$", iec_code):
            messages.error(request, "IEC Code must be exactly 10 alphanumeric characters.")
            return render(request, 'buyerregister.html')

        # D. Address Validation
        if len(village) < 2 or len(district) < 2:
            messages.error(request, "City and District must contain at least 2 characters.")
            return render(request, 'buyerregister.html')
            
        if not re.match(r"^\d{6}$", pincode):
            messages.error(request, "Pincode must be exactly 6 digits.")
            return render(request, 'buyerregister.html')

        # ==========================================
        # SMART GEOCODING (Fixing the 0.0 Atlantic Ocean Bug)
        # ==========================================
        geo_engine = IndianAgriGeocoder()
        mapped_lat, mapped_lon = geo_engine.get_coordinates(district, state)

        # ==========================================
        # DATABASE TRANSACTION
        # ==========================================
        try:
            with transaction.atomic():
                # Step 1: Create Corporate User
                user = User.objects.create_user(
                    username=name,
                    email=email,
                    password=password,
                    role=User.Role.BUYER,
                    is_verified=False, # Must be approved by Admin!
                )
                
                # Step 2: Create Geocoded Address
                Address.objects.create(
                    user=user,
                    village=village,
                    district=district,
                    state=state,
                    pincode=pincode,
                    latitude=mapped_lat, 
                    longitude=mapped_lon
                )

                # Step 3: Create Buyer Profile
                BuyerProfile.objects.create(
                    user=user,
                    company_name=company_name,
                    gst_number=gst_number,
                    iec_code=iec_code,
                    apeda_org=apeda_org
                )

                # Step 4: Send Onboarding Email
                subject = "Kultiva - Corporate Buyer Registration Pending"
                message = f"""
                Hello {name},

                Your company '{company_name}' has been successfully registered on Kultiva. 
                Your account is currently under review by our Admin team for GST and IEC compliance.
                
                You will receive an email once your corporate Escrow Vault is activated.
                
                Regards,
                Kultiva Enterprise
                """
                send_mail(subject, message, 'admin@kultiva.com', [email], fail_silently=False)

                return render(request, 'registration_success.html')

        except Exception as e:
            logger.error(f"Error registering buyer: {e}")
            messages.error(request, 'An unexpected system error occurred during registration. Please try again.')
            return render(request, 'buyerregister.html')

    return render(request, 'buyerregister.html')


def addseller(request):
    if request.method == 'POST':
        # 1. Collect & Sanitize User Data (Prevent XSS)
        name = strip_tags(request.POST.get('name', '')).strip()
        email = strip_tags(request.POST.get('email', '')).strip()
        password = request.POST.get('password', '')

        # 2. Collect & Sanitize Address Data
        village = strip_tags(request.POST.get('village', '')).strip()
        district = strip_tags(request.POST.get('district', '')).strip()
        state = strip_tags(request.POST.get('state', '')).strip()
        pincode = strip_tags(request.POST.get('pincode', '')).strip()

        # 3. Collect & Sanitize Seller Profile Data
        shop_name = strip_tags(request.POST.get('shop_name', '')).strip()
        license_number = strip_tags(request.POST.get('license_number', '')).strip().upper()
        gst_number = strip_tags(request.POST.get('gst_number', '')).strip().upper()
        # Truncate description at 500 chars maximum and strip HTML
        description = strip_tags(request.POST.get('description', '')).strip()[:500] 

        # ==========================================
        # HARD BACKEND VALIDATION ENGINE
        # ==========================================
        
        # A. Name & Email Validation
        if len(name) < 3 or not re.match(r"^[A-Za-z\s]+$", name):
            messages.error(request, "Name must be at least 3 characters and contain only letters.")
            return render(request, 'sellerregister.html')

        try:
            validate_email(email)
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "This email is already registered globally in our system.")
                return render(request, 'sellerregister.html')
        except ValidationError:
            messages.error(request, "Invalid email format.")
            return render(request, 'sellerregister.html')

        # B. Password Validation (Financial Security)
        pass_regex = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
        if not re.match(pass_regex, password):
            messages.error(request, "Password must be at least 8 characters long and include an uppercase letter, lowercase letter, number, and special character.")
            return render(request, 'sellerregister.html')

        # C. Shop & Legal Credentials Validation
        if len(shop_name) < 3 or not re.match(r"^[A-Za-z0-9\s.,&'-]+$", shop_name):
            messages.error(request, "Invalid Shop Name format. Minimum 3 characters required.")
            return render(request, 'sellerregister.html')
            
        if SellerProfile.objects.filter(shop_name__iexact=shop_name).exists():
            messages.error(request, "This Shop Name is already registered on Kultiva.")
            return render(request, 'sellerregister.html')

        # License Number Validation (Alphanumeric, 6-20 chars)
        if not re.match(r"^[A-Z0-9]{6,20}$", license_number):
            messages.error(request, "Invalid License Number format.")
            return render(request, 'sellerregister.html')
            
        if SellerProfile.objects.filter(license_number=license_number).exists():
            messages.error(request, "This License Number is already registered.")
            return render(request, 'sellerregister.html')

        # GST format check (Strict Indian 15-char format)
        if not re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$", gst_number):
            messages.error(request, "GST Number must follow the exact 15-character Indian format.")
            return render(request, 'sellerregister.html')
            
        # Check if GST is already used by another Seller OR Buyer
        if SellerProfile.objects.filter(gst_number=gst_number).exists() or BuyerProfile.objects.filter(gst_number=gst_number).exists():
            messages.error(request, "This GST Number is already tied to an existing corporate account.")
            return render(request, 'sellerregister.html')

        # D. Address Validation
        if len(village) < 2 or len(district) < 2:
            messages.error(request, "City and District must contain at least 2 characters.")
            return render(request, 'sellerregister.html')
            
        if not re.match(r"^\d{6}$", pincode):
            messages.error(request, "Pincode must be exactly 6 digits.")
            return render(request, 'sellerregister.html')

        # ==========================================
        # SMART GEOCODING (Fixing the 0.0 Atlantic Ocean Bug)
        # ==========================================
        geo_engine = IndianAgriGeocoder()
        mapped_lat, mapped_lon = geo_engine.get_coordinates(district, state)

        # ==========================================
        # DATABASE TRANSACTION
        # ==========================================
        try:
            with transaction.atomic():
                # Step 1: Create User (EXPLICITLY set as unverified to block login/listing)
                user = User.objects.create_user(
                    username=name,
                    email=email,
                    password=password,
                    role=User.Role.SELLER,
                    is_verified=False 
                )

                # Step 2: Create Geocoded Address
                Address.objects.create(
                    user=user,
                    village=village,
                    district=district,
                    state=state,
                    pincode=pincode,
                    latitude=mapped_lat, 
                    longitude=mapped_lon
                )

                # Step 3: Create Seller Profile
                SellerProfile.objects.create(
                    user=user,
                    shop_name=shop_name,
                    license_number=license_number,
                    gst_number=gst_number,
                    description=description
                )

                # Step 4: Send Onboarding Email
                subject = "Kultiva - Seller Registration Under Review"
                message = f"""
                Hello {name},

                Your shop '{shop_name}' has been successfully registered on Kultiva. 
                For the security of our farmers, your account is currently under review by our Admin team to verify your Trade License and GST documents.
                
                You will not be able to list products on the marketplace until this verification is complete. We will email you once your storefront is approved.
                
                Regards,
                Kultiva Seller Support
                """
                send_mail(subject, message, 'admin@kultiva.com', [email], fail_silently=False)

                return render(request, 'registration_success.html')

        except Exception as e:
            logger.error(f"Error registering seller: {e}")
            messages.error(request, 'An unexpected system error occurred during registration. Please try again.')
            return render(request, 'sellerregister.html')

    return render(request, 'sellerregister.html')

# --- MARKETPLACE LISTINGS ---
@login_required
def add_listing(request):
    # Security: Only Farmers and Sellers can add items
    if request.user.role not in [User.Role.FARMER, User.Role.SELLER]:
        messages.error(request, "Access Denied. Only Farmers and Sellers can add listings.")
        return redirect('index')

    if request.method == 'POST':
        # 1. Fetch data from form
        wing = request.POST.get('wing')
        category = request.POST.get('category')
        title = request.POST.get('title')
        variety = request.POST.get('variety_or_brand', '') # Optional
        price = request.POST.get('price')
        uom = request.POST.get('unit_of_measure')
        stock = request.POST.get('available_stock')
        description = request.POST.get('description')
        image = request.FILES.get('image')

        # 2. Backend Validation (Double checking in case JS was bypassed)
        if not all([wing, category, title, price, uom, stock, description, image]):
            messages.error(request, "Error: Please fill in all required fields.")
            return render(request, 'add_listing.html')

        try:
            price = float(price)
            stock = float(stock)
            
            if price <= 0 or stock <= 0:
                messages.error(request, "Error: Price and Stock must be greater than zero.")
                return render(request, 'add_listing.html')

            # 3. Save to Database
            MarketplaceListing.objects.create(
                listed_by=request.user,
                wing=wing,
                category=category,
                title=title,
                variety_or_brand=variety,
                price=price,
                unit_of_measure=uom,
                available_stock=stock,
                description=description,
                image=image,
                status='ACTIVE'
            )
            
            # 4. Success Notification
            messages.success(request, f"Success! '{title}' has been listed on the marketplace.")
            return redirect('add_listing') # Refreshes the page with an empty form

        except ValueError:
            messages.error(request, "Error: Invalid number format for Price or Stock.")
            return render(request, 'add_listing.html')
            
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")
            return render(request, 'add_listing.html')

    # If GET request, just load the form
    return render(request, 'add_listing.html')

# --- 1. VIEW MANAGE STOCK PAGE ---
@login_required
def manage_stock(request):
    if request.user.role != User.Role.SELLER:
        return redirect('index')
    
    # Fetch all items listed by this specific seller
    listings = MarketplaceListing.objects.filter(listed_by=request.user).order_by('-created_at')
    return render(request, 'manage_stock.html', {'listings': listings})

# --- Helper Function for HTML Email ---
def send_stock_email(user, listing_title, action_type):
    subject = f"Kultiva Update: Product {action_type}"
    color = "#fbc02d" if action_type == "Updated" else "#dc3545"
    
    # A beautiful, colorful HTML email structure
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f1f8e9; padding: 30px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; border-top: 6px solid {color}; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #1b5e20; margin-bottom: 20px;">Kultiva Inventory Notice</h2>
                <p style="font-size: 16px; color: #333;">Hello <strong>{user.username}</strong>,</p>
                <div style="background-color: #f9f9f9; border-left: 4px solid {color}; padding: 15px; margin: 20px 0;">
                    <p style="font-size: 16px; margin: 0;">Your product <strong>'{listing_title}'</strong> has been successfully <strong>{action_type.lower()}</strong> in the Kultiva marketplace.</p>
                </div>
                <p style="font-size: 14px; color: #666;">If you did not perform this action, please contact Admin immediately.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="font-size: 12px; color: #999; text-align: center;">&copy; 2026 Kultiva Agricultural Network. All rights reserved.</p>
            </div>
        </body>
    </html>
    """
    
    plain_message = strip_tags(html_message) # Fallback for email clients that don't support HTML
    send_mail(subject, plain_message, 'admin@kultiva.com', [user.email], html_message=html_message, fail_silently=False)

# --- 2. REMOVE STOCK FUNCTION ---
@login_required
def remove_listing(request):
    if request.method == 'POST':
        listing_id = request.POST.get('listing_id')
        # Ensure the seller only deletes THEIR OWN item
        listing = get_object_or_404(MarketplaceListing, id=listing_id, listed_by=request.user)
        
        title = listing.title
        listing.delete()
        
        # Trigger the beautiful HTML email
        send_stock_email(request.user, title, "Removed")
        
        messages.success(request, f"Item '{title}' successfully removed. An email confirmation has been sent.")
    
    return redirect('manage_stock')

# --- 3. EDIT STOCK FUNCTION ---
@login_required
def edit_listing(request, listing_id):
    # 1. Fetch the listing, ensuring it belongs to the logged-in user
    listing = get_object_or_404(MarketplaceListing, id=listing_id, listed_by=request.user)

    if request.method == 'POST':
        try:
            # 2. Safely capture the incoming form data
            title = request.POST.get('title')
            variety = request.POST.get('variety_or_brand')
            price_str = request.POST.get('price')
            stock_str = request.POST.get('available_stock')
            description = request.POST.get('description')
            status = request.POST.get('status')
            
            # 3. Server-Side Validation (Never trust the frontend alone!)
            if not title or not price_str or not stock_str or not description:
                messages.error(request, "Critical fields cannot be empty.")
                return redirect('edit_listing', listing_id=listing.id)

            # 4. Apply updates with safe Type Casting
            listing.title = title.strip()
            listing.variety_or_brand = variety.strip() if variety else ""
            listing.price = float(price_str)
            listing.available_stock = float(stock_str)
            listing.description = description.strip()
            listing.status = status
            
            # 5. Handle the optional image upload
            if request.FILES.get('image'):
                listing.image = request.FILES.get('image')
                
            # 6. Save to the database
            listing.save()
            
            # 7. Trigger the beautiful HTML email notification
            send_stock_email(request.user, listing.title, "Updated")
            
            # 8. Success Feedback
            messages.success(request, f"'{listing.title}' has been successfully updated. Notification sent.")
            return redirect('manage_stock')

        except ValueError:
            # Catches errors if someone tries to submit text instead of numbers for price/stock
            messages.error(request, "Invalid number format provided for price or stock.")
            return redirect('edit_listing', listing_id=listing.id)
            
        except Exception as e:
            # The ultimate safety net so your server never crashes
            messages.error(request, f"An unexpected error occurred: {e}")
            return redirect('edit_listing', listing_id=listing.id)

    # If it's a GET request, just render the beautiful form
    return render(request, 'edit_listing.html', {'listing': listing})


def login_view(request):
    if request.method == 'POST':
        # 1. Get Email & Password from the form
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            # 2. Find the User by Email
            # We use .filter().first() to avoid crashing if the email doesn't exist
            user_obj = User.objects.filter(email=email).first()

            if user_obj is not None:
                # 3. Authenticate using the FOUND username and the entered password
                user = authenticate(username=user_obj.username, password=password)

                if user is not None:
                    # 4. Check Verification Status (SRS Requirement)
                    if not user.is_verified:
                        messages.error(request, "Your account is pending admin approval.")
                        return redirect('login')
                    
                    # 5. Login Success
                    login(request, user)
                    
                    # Redirect based on Role
                    if user.role == User.Role.FARMER:
                        return redirect('farmer_home')
                    elif user.role == User.Role.BUYER:
                        return redirect('buyer_dashboard')
                    elif user.role == User.Role.SELLER:
                        return redirect('seller_dashboard')
                    elif user.role == User.Role.ADMIN:
                        return redirect('admin_dashboard') 
                else:
                    messages.error(request, "Incorrect password.")
            else:
                messages.error(request, "No account found with this email.")

        except Exception as e:
            messages.error(request, f"Login Error: {e}")
            
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')


# 1. THE DASHBOARD VIEW
@login_required
def admin_dashboard(request):
    # Security Check: Only allow Admins
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('index')

    # Fetch all users who are NOT verified yet
    pending_farmers = User.objects.filter(role=User.Role.FARMER, is_verified=False)
    pending_buyers = User.objects.filter(role=User.Role.BUYER, is_verified=False)

    context = {
        'pending_farmers': pending_farmers,
        'pending_buyers': pending_buyers
    }
    return render(request, 'admin_dashboard.html', context)

# 2. THE APPROVE ACTION
@login_required
def approve_user(request, user_id):
    # Security Check
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        return redirect('index')

    # Find the user and verify them
    user = get_object_or_404(User, pk=user_id)
    user.is_verified = True
    user.save()
    
    messages.success(request, f"User {user.username} has been verified!")
    return redirect('admin_dashboard')

# --- 1. UPDATED MANAGE FARMERS VIEW ---
@login_required
def manage_farmers(request):
    # Security Check
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('index')

    # Get Search & Filter Parameters
    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('status', 'all')

    # Base Query: All Farmers
    farmers = User.objects.filter(role=User.Role.FARMER).order_by('-date_joined')

    # Apply Search (Name or Email)
    if search_query:
        farmers = farmers.filter(
            Q(username__icontains=search_query) | 
            Q(email__icontains=search_query)
        )

    # Apply Filters
    if filter_status == 'approved':
        farmers = farmers.filter(is_verified=True, is_active=True)
    elif filter_status == 'pending':
        farmers = farmers.filter(is_verified=False, is_active=True)
    elif filter_status == 'removed':
        farmers = farmers.filter(is_active=False)

    context = {
        'farmers': farmers,
        'search_query': search_query,
        'filter_status': filter_status
    }
    return render(request, 'manage_farmers.html', context)

# --- 2. NEW ACTION VIEW (HANDLES POPUP SUBMISSION) ---
@login_required
def farmer_action(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action_type')
        email_message = request.POST.get('email_message')

        # --- FIX START: Check if ID is empty ---
        if not user_id:
            messages.error(request, "Error: User ID was missing. Please try again.")
            return redirect('manage_farmers')
        # --- FIX END ---
        
        # Now it is safe to search
        user = get_object_or_404(User, pk=user_id)
        
        try:
            subject = "Kultiva Account Update"
            
            # ... rest of your logic (Approve/Reject/Remove) ...
            if action == 'approve':
                user.is_verified = True
                user.is_active = True
                user.save()
                subject = "Congratulations! Your Kultiva Account is Approved"
                messages.success(request, f"Farmer {user.username} approved successfully.")

            elif action == 'reject':
                user.is_verified = False
                user.is_active = False 
                user.save()
                subject = "Update regarding your Kultiva Registration"
                messages.warning(request, f"Farmer {user.username} registration rejected.")

            elif action == 'remove':
                user.is_active = False
                user.save()
                subject = "Important: Your Kultiva Account has been Suspended"
                messages.error(request, f"Farmer {user.username} has been removed.")

            # Send Email
            if user.email:
                full_message = f"Hello {user.username},\n\n{email_message}\n\nRegards,\nTeam Kultiva Admin"
                send_mail(subject, full_message, 'admin@kultiva.com', [user.email], fail_silently=True)

        except Exception as e:
            messages.error(request, f"Error processing action: {e}")

    return redirect('manage_farmers')
# 1. VIEW PROFILE FUNCTION
@login_required
def view_farmer_profile(request, user_id):
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        return redirect('index')
        
    farmer = get_object_or_404(User, pk=user_id)
    return render(request, 'view_farmer_profile.html', {'farmer': farmer})

# 2. SEND EMAIL FUNCTION (Directly from Profile)
@login_required
def send_farmer_email(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        user = get_object_or_404(User, pk=user_id)
        
        try:
            full_message = f"Hello {user.username},\n\n{message}\n\nRegards,\nTeam Kultiva Admin"
            
            send_mail(
                subject,
                full_message,
                'admin@kultiva.com',
                [user.email],
                fail_silently=False,
            )
            messages.success(request, f"Email sent successfully to {user.username}!")
        except Exception as e:
            messages.error(request, f"Failed to send email: {e}")
            
        return redirect('view_farmer_profile', user_id=user.pk)
        
    return redirect('manage_farmers')

# --- 3. MANAGE BUYERS VIEW ---
@login_required
def manage_buyers(request):
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('index')

    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('status', 'all')

    # Base Query: All BUYERS
    buyers = User.objects.filter(role=User.Role.BUYER).order_by('-date_joined')

    # Search
    if search_query:
        buyers = buyers.filter(
            Q(username__icontains=search_query) | 
            Q(email__icontains=search_query) 
            # Note: Searching company_name would require joining the profile table
        )

    # Filters
    if filter_status == 'approved':
        buyers = buyers.filter(is_verified=True, is_active=True)
    elif filter_status == 'pending':
        buyers = buyers.filter(is_verified=False, is_active=True)
    elif filter_status == 'removed':
        buyers = buyers.filter(is_active=False)

    context = {
        'buyers': buyers,
        'search_query': search_query,
        'filter_status': filter_status
    }
    return render(request, 'manage_buyers.html', context)

# --- 4. BUYER ACTION VIEW (Handles Popup) ---
@login_required
def buyer_action(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action_type')
        email_message = request.POST.get('email_message')

        # ERROR CHECK from previous lesson
        if not user_id:
            messages.error(request, "Error: User ID was missing. Please try again.")
            return redirect('manage_buyers')

        user = get_object_or_404(User, pk=user_id)
        
        try:
            subject = "Kultiva Business Account Update"
            
            if action == 'approve':
                user.is_verified = True
                user.is_active = True
                user.save()
                subject = "Account Approved - Welcome to Kultiva"
                messages.success(request, f"Buyer {user.username} approved successfully.")

            elif action == 'reject':
                user.is_verified = False
                user.is_active = False 
                user.save()
                subject = "Kultiva Registration Status"
                messages.warning(request, f"Buyer {user.username} registration rejected.")

            elif action == 'remove':
                user.is_active = False
                user.save()
                subject = "Account Suspension Notice"
                messages.error(request, f"Buyer {user.username} has been removed.")

            # Send Email
            if user.email:
                full_message = f"Hello {user.username},\n\n{email_message}\n\nRegards,\nTeam Kultiva Admin"
                send_mail(subject, full_message, 'admin@kultiva.com', [user.email], fail_silently=True)
            
        except Exception as e:
            messages.error(request, f"Error processing action: {e}")

    return redirect('manage_buyers')

# --- 1. VIEW BUYER PROFILE ---
@login_required
def view_buyer_profile(request, user_id):
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        return redirect('index')
        
    buyer = get_object_or_404(User, pk=user_id)
    return render(request, 'view_buyer_profile.html', {'buyer': buyer})

# --- 2. SEND EMAIL TO BUYER ---
@login_required
def send_buyer_email(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        user = get_object_or_404(User, pk=user_id)
        
        try:
            full_message = f"Hello {user.username},\n\n{message}\n\nRegards,\nTeam Kultiva Admin"
            
            send_mail(
                subject,
                full_message,
                'admin@kultiva.com',
                [user.email],
                fail_silently=False,
            )
            messages.success(request, f"Email sent successfully to {user.username}!")
        except Exception as e:
            messages.error(request, f"Failed to send email: {e}")
            
        return redirect('view_buyer_profile', user_id=user.pk)
        
    return redirect('manage_buyers')

# --- 5. MANAGE SELLERS VIEW ---
@login_required
def manage_sellers(request):
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, "Access Denied.")
        return redirect('index')

    search_query = request.GET.get('search', '')
    filter_status = request.GET.get('status', 'all')

    # Base Query: All SELLERS
    sellers = User.objects.filter(role=User.Role.SELLER).order_by('-date_joined')

    # Search
    if search_query:
        sellers = sellers.filter(
            Q(username__icontains=search_query) | 
            Q(email__icontains=search_query)
        )

    # Filters
    if filter_status == 'approved':
        sellers = sellers.filter(is_verified=True, is_active=True)
    elif filter_status == 'pending':
        sellers = sellers.filter(is_verified=False, is_active=True)
    elif filter_status == 'removed':
        sellers = sellers.filter(is_active=False)

    context = {
        'sellers': sellers,
        'search_query': search_query,
        'filter_status': filter_status
    }
    return render(request, 'manage_sellers.html', context)

# --- 6. SELLER ACTION VIEW (Handles Popup) ---
@login_required
def seller_action(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action_type')
        email_message = request.POST.get('email_message')

        if not user_id:
            messages.error(request, "Error: User ID was missing.")
            return redirect('manage_sellers')

        user = get_object_or_404(User, pk=user_id)
        
        try:
            subject = "Kultiva Seller Account Update"
            
            if action == 'approve':
                user.is_verified = True
                user.is_active = True
                user.save()
                subject = "Account Approved - Start Selling on Kultiva"
                messages.success(request, f"Seller {user.username} approved successfully.")

            elif action == 'reject':
                user.is_verified = False
                user.is_active = False 
                user.save()
                subject = "Kultiva Seller Registration Status"
                messages.warning(request, f"Seller {user.username} registration rejected.")

            elif action == 'remove':
                user.is_active = False
                user.save()
                subject = "Account Suspension Notice"
                messages.error(request, f"Seller {user.username} has been removed.")

            # Send Email
            if user.email:
                full_message = f"Hello {user.username},\n\n{email_message}\n\nRegards,\nTeam Kultiva Admin"
                send_mail(subject, full_message, 'admin@kultiva.com', [user.email], fail_silently=True)
            
        except Exception as e:
            messages.error(request, f"Error processing action: {e}")

    return redirect('manage_sellers')

# --- 7. VIEW SELLER PROFILE ---
@login_required
def view_seller_profile(request, user_id):
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        return redirect('index')
        
    seller = get_object_or_404(User, pk=user_id)
    return render(request, 'view_seller_profile.html', {'seller': seller})

# --- 8. SEND EMAIL TO SELLER ---
@login_required
def send_seller_email(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        user = get_object_or_404(User, pk=user_id)
        
        try:
            full_message = f"Hello {user.username},\n\n{message}\n\nRegards,\nTeam Kultiva Admin"
            
            send_mail(
                subject,
                full_message,
                'admin@kultiva.com',
                [user.email],
                fail_silently=False,
            )
            messages.success(request, f"Email sent successfully to {user.username}!")
        except Exception as e:
            messages.error(request, f"Failed to send email: {e}")
            
        return redirect('view_seller_profile', user_id=user.pk)
        
    return redirect('manage_sellers')

# --- 10. ADMIN: MANAGE SOIL REPORTS ---
@login_required
def manage_soil_reports(request):
    if request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        return redirect('index')
    
    # Fetch all reports, putting the newest requests at the top
    reports = ManualSoilReport.objects.all().order_by('-request_date')
    return render(request, 'manage_soil_reports.html', {'reports': reports})

@login_required
def update_soil_report(request):
    if request.method == 'POST' and (request.user.role == User.Role.ADMIN or request.user.is_superuser):
        try:
            report_id = request.POST.get('report_id')
            status = request.POST.get('status')
            admin_message = request.POST.get('admin_message', '').strip()
            
            report = get_object_or_404(ManualSoilReport, id=report_id)
            
            # --- THE SMART FOLLOW-UP CHECK ---
            # If it was ALREADY completed, and the admin is just sending a message
            is_followup = (report.request_status == 'COMPLETED' and status == 'COMPLETED')
            
            # 1. Update the database status
            report.request_status = status
            
            # 2. Only save NPK/pH data if the test is NEWLY completed (protects existing data)
            if status == 'COMPLETED' and not is_followup:
                ph = request.POST.get('ph')
                n = request.POST.get('n')
                p = request.POST.get('p')
                k = request.POST.get('k')
                
                report.ph = float(ph) if ph else None
                report.n = float(n) if n else None
                report.p = float(p) if p else None
                report.k = float(k) if k else None
            
            report.save()

            # --- GENERATE THE HTML EMAIL ---
            farmer = report.farmer
            
            # Adjust Email Subject and Header based on Mode
            if is_followup:
                subject = f"Kultiva Lab Update: Follow-up Message"
                status_badge = "FOLLOW-UP MESSAGE"
                intro_text = "You have received a new follow-up message regarding your completed soil test."
            else:
                subject = f"Kultiva Lab Update: Soil Test Status - {status}"
                status_badge = status
                intro_text = "There has been an update regarding your recent soil testing request."
            
            # Dynamic Results Block
            results_html = ""
            if status == 'COMPLETED':
                results_html = f"""
                <div style="background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 8px; padding: 15px; margin-top: 20px;">
                    <h4 style="color: #2e7d32; margin-top: 0; border-bottom: 2px solid #c5e1a5; padding-bottom: 5px;">Official Lab Results</h4>
                    <table style="width: 100%; font-size: 14px; color: #333;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>pH Level:</strong></td><td style="text-align: right; font-weight: bold; color: #1b5e20;">{report.ph}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Nitrogen (N):</strong></td><td style="text-align: right; font-weight: bold; color: #1b5e20;">{report.n}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Phosphorus (P):</strong></td><td style="text-align: right; font-weight: bold; color: #1b5e20;">{report.p}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Potassium (K):</strong></td><td style="text-align: right; font-weight: bold; color: #1b5e20;">{report.k}</td>
                        </tr>
                    </table>
                </div>
                """

            html_message = f"""
            <html>
            <body style="font-family: 'Times New Roman', Times, serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 16px rgba(0,0,0,0.1);">
                    <div style="background: linear-gradient(135deg, #1b5e20, #2e7d32); color: #ffffff; padding: 25px; text-align: center;">
                        <h2 style="margin: 0; color: #fbc02d; font-size: 28px; letter-spacing: 1px;">KULTIVA LABS</h2>
                        <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Soil Health Analysis</p>
                    </div>
                    
                    <div style="padding: 30px; color: #333333;">
                        <h3 style="color: #1e293b;">Hello {farmer.username},</h3>
                        <p style="font-size: 15px; line-height: 1.6;">{intro_text}</p>
                        
                        <div style="background-color: #fffde7; border-left: 5px solid #fbc02d; padding: 15px; margin: 20px 0; border-radius: 4px;">
                            <strong style="color: #f57f17; font-size: 12px; text-transform: uppercase;">Current Status</strong><br>
                            <span style="font-size: 18px; font-weight: bold; color: #333;">{status_badge}</span>
                        </div>
                        
                        {f'<p style="background: #f8f9fa; padding: 15px; border-radius: 8px; font-style: italic; border-left: 3px solid #ccc;">" {admin_message} "</p>' if admin_message else ''}
                        
                        {results_html}

                        <p style="margin-top: 30px; font-size: 14px; color: #666;">Log in to your Farmer Dashboard to view how these updates affect your AI Crop Recommendations.</p>
                        <p style="margin-bottom: 0;">Regards,<br><strong style="color: #1b5e20;">The Kultiva Agronomy Team</strong></p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            plain_message = strip_tags(html_message)

            send_mail(
                subject=subject,
                message=plain_message,
                from_email='admin@kultiva.com',
                recipient_list=[farmer.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            messages.success(request, f"Successfully processed request for {farmer.username} and sent notification email.")
            
        except Exception as e:
            messages.error(request, f"Error updating report: {e}")

    return redirect('manage_soil_reports')

# =========================================================
# --- ADMIN: ESCROW & DISPUTE RESOLUTION CENTER ---
# =========================================================

# --- 1. B2B ESCROW MANAGEMENT (Corporate Buyers & Harvests) ---
@login_required
def manage_b2b_refunds(request):
    # Strict Security Gate
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied. Admin privileges required.")
        return redirect('index')

    try:
        # Fetch all Escrow funds that are currently LOCKED
        # We filter for buyers to separate B2B from B2C
        locked_escrows = EscrowTransaction.objects.filter(
            payment_status='ESCROW_LOCKED',
            purchaser__role=User.Role.BUYER
        ).select_related('purchaser', 'vendor', 'item_purchased').order_by('-created_at')

        context = {
            'locked_escrows': locked_escrows
        }
        return render(request, 'manage_b2b_refunds.html', context)
    except Exception as e:
        messages.error(request, f"Error loading B2B Escrow module: {e}")
        return redirect('admin_dashboard')

# --- NEW: THE DEDICATED CASE REVIEW DASHBOARD ---
@login_required
def admin_b2b_refund_detail(request, transaction_id):
    # Strict Security Gate
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied. Admin privileges required.")
        return redirect('index')

    try:
        # 1. Fetch the specific escrow transaction securely
        txn = get_object_or_404(EscrowTransaction, transaction_id=transaction_id)
        
        # Verify it is actually a Corporate Buyer (B2B) transaction
        if txn.purchaser.role != User.Role.BUYER:
            messages.error(request, "Invalid transaction routing.")
            return redirect('manage_b2b_refunds')

        # 2. Advanced Contract Matching: Fetch the original proposal for full specs
        b2b_trade = None
        if txn.security_token:
            b2b_trade = DirectTradeProposal.objects.filter(security_token=txn.security_token).first()
        if not b2b_trade and txn.item_purchased:
            b2b_trade = DirectTradeProposal.objects.filter(listing=txn.item_purchased, buyer=txn.purchaser).first()

        # 3. Handle Custom Investigation Emails (Messaging both parties)
        if request.method == 'POST' and request.POST.get('action') == 'send_investigation_email':
            custom_message = request.POST.get('custom_message', '').strip()
            
            if custom_message:
                subject = f"Kultiva Admin Investigation: Escrow Dispute {transaction_id}"
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
                        <div style="background-color: #f57f17; padding: 20px; text-align: center; color: white;">
                            <h2 style="margin: 0; font-size: 22px;">Official Admin Communication</h2>
                        </div>
                        <div style="padding: 30px; color: #333;">
                            <p style="font-size: 15px; color: #555;">An update regarding the disputed transaction <strong>{transaction_id}</strong>:</p>
                            
                            <div style="background: #fff8e1; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #fbc02d;">
                                <p style="margin: 0; color: #333; font-size: 15px; font-style: italic;">"{custom_message}"</p>
                            </div>
                            
                            <p style="font-size: 14px; color: #64748b;">Please reply directly to this email if you need to provide further evidence (photos, delivery receipts, etc.) before a final decision is made.</p>
                            <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Trust & Safety Team</p>
                        </div>
                    </div>
                </div>
                """
                # Dispatch the email simultaneously to both the buyer and the vendor
                from django.utils.html import strip_tags
                send_mail(
                    subject, 
                    strip_tags(html_message), 
                    'admin@kultiva.com', 
                    [txn.purchaser.email, txn.vendor.email], 
                    html_message=html_message, 
                    fail_silently=True
                )
                
                messages.success(request, "Investigation email successfully dispatched to both parties.")
                return redirect('admin_b2b_refund_detail', transaction_id=transaction_id)

        # 4. Package data for the UI
        context = {
            'txn': txn,
            'buyer': txn.purchaser,
            'vendor': txn.vendor,
            'listing': txn.item_purchased,
            'b2b_trade': b2b_trade,
        }
        return render(request, 'admin_b2b_refund_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading case details: {e}")
        return redirect('manage_b2b_refunds')


@login_required
def process_b2b_refund(request, transaction_id):
    if request.user.role != User.Role.ADMIN or request.method != 'POST':
        return redirect('index')

    try:
        txn = get_object_or_404(EscrowTransaction, transaction_id=transaction_id)
        action = request.POST.get('action')

        if action == 'refund':
            txn.payment_status = 'REFUNDED'
            txn.save()
            messages.success(request, f"Funds strictly REFUNDED to Buyer: {txn.purchaser.username}.")
            
            # --- BEAUTIFUL HTML EMAIL: REFUND TO BUYER ---
            subject = f"Kultiva Escrow: Dispute Resolved & Refund Processed"
            html_message = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                    <div style="background-color: #d32f2f; padding: 20px; text-align: center; color: white;">
                        <h2 style="margin: 0; font-size: 24px;">Refund Processed</h2>
                    </div>
                    <div style="padding: 30px; color: #333;">
                        <p style="font-size: 16px;">Dear <strong>{txn.purchaser.username}</strong>,</p>
                        <p style="font-size: 15px; color: #555;">The Kultiva Admin team has reviewed your dispute regarding transaction <strong>{transaction_id}</strong>. The dispute has been resolved in your favor.</p>
                        
                        <div style="background: #f1f5f9; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #d32f2f;">
                            <h3 style="margin: 0 0 10px 0; color: #1e293b;">Refund Details</h3>
                            <p style="margin: 5px 0;"><strong>Amount Refunded:</strong> <span style="color: #d32f2f; font-size: 18px; font-weight: bold;">₹{txn.amount_paid}</span></p>
                            <p style="margin: 5px 0;"><strong>Original Vendor:</strong> {txn.vendor.username}</p>
                        </div>
                        
                        <p style="font-size: 14px; color: #64748b;">The funds have been returned to your original payment method. Please allow 3-5 business days for it to reflect in your account.</p>
                        <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Trust & Safety Team</p>
                    </div>
                </div>
            </div>
            """
            send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', [txn.purchaser.email], html_message=html_message, fail_silently=True)

        elif action == 'release':
            txn.payment_status = 'COMPLETED'
            txn.save()
            messages.success(request, f"Funds FORCE-RELEASED to Vendor: {txn.vendor.username}.")
            
            # --- BEAUTIFUL HTML EMAIL: RELEASE TO VENDOR ---
            subject = f"Kultiva Escrow: Dispute Resolved & Funds Released"
            html_message = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                    <div style="background-color: #1b5e20; padding: 20px; text-align: center; color: white;">
                        <h2 style="margin: 0; font-size: 24px;">Funds Released</h2>
                    </div>
                    <div style="padding: 30px; color: #333;">
                        <p style="font-size: 16px;">Dear <strong>{txn.vendor.username}</strong>,</p>
                        <p style="font-size: 15px; color: #555;">The Kultiva Admin team has concluded the review of the disputed transaction <strong>{transaction_id}</strong>. The hold has been lifted and the funds have been forcefully released to your account.</p>
                        
                        <div style="background: #f1f8e9; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #2e7d32;">
                            <h3 style="margin: 0 0 10px 0; color: #1e293b;">Payment Details</h3>
                            <p style="margin: 5px 0;"><strong>Amount Released:</strong> <span style="color: #1b5e20; font-size: 18px; font-weight: bold;">₹{txn.amount_paid}</span></p>
                            <p style="margin: 5px 0;"><strong>Purchaser:</strong> {txn.purchaser.username}</p>
                        </div>
                        
                        <p style="font-size: 14px; color: #64748b;">Thank you for your patience and for being a trusted supplier on our platform.</p>
                        <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Trust & Safety Team</p>
                    </div>
                </div>
            </div>
            """
            send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', [txn.vendor.email], html_message=html_message, fail_silently=True)

    except Exception as e:
        messages.error(request, f"Error processing B2B transaction: {e}")

    return redirect('manage_b2b_refunds')


# =========================================================
# --- 2. B2C REFUND MANAGEMENT (Farmers & Seed Orders) ---
# =========================================================

@login_required
def manage_b2c_refunds(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied. Admin privileges required.")
        return redirect('index')

    try:
        # 1. Fetch ONLY orders that are strictly 'CANCELLED'
        # (Once we refund them, they will drop off this list instantly!)
        cancelled_orders = InputOrder.objects.filter(
            status='CANCELLED'
        ).exclude(payment_method='COD').select_related('farmer', 'product__listed_by').order_by('-created_at')

        orders_data = []
        for order in cancelled_orders:
            # 2. Precise Match
            escrow = EscrowTransaction.objects.filter(security_token=f'ORDER-{order.order_id}').first()
            
            # 3. PRO FIX: Strict Fallback matching! 
            # We use .order_by('-created_at') to ensure we don't accidentally grab an older, successful purchase of the same seed.
            if not escrow:
                escrow = EscrowTransaction.objects.filter(
                    purchaser=order.farmer, 
                    item_purchased=order.product
                ).order_by('-created_at').first() 
            
            orders_data.append({
                'order': order,
                'escrow': escrow
            })

        context = {
            'orders_data': orders_data
        }
        return render(request, 'manage_b2c_refunds.html', context)
    except Exception as e:
        messages.error(request, f"Error loading B2C Refund module: {e}")
        return redirect('admin_dashboard')


# --- NEW: B2C CASE REVIEW DASHBOARD ---
@login_required
def admin_b2c_refund_detail(request, order_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        order = get_object_or_404(InputOrder, order_id=order_id)
        
        escrow = EscrowTransaction.objects.filter(security_token=f'ORDER-{order.order_id}').first()
        if not escrow:
            escrow = EscrowTransaction.objects.filter(
                purchaser=order.farmer, 
                item_purchased=order.product
            ).order_by('-created_at').first()

        # Handle Custom Investigation Emails
        if request.method == 'POST' and request.POST.get('action') == 'send_investigation_email':
            custom_message = request.POST.get('custom_message', '').strip()
            if custom_message:
                subject = f"Kultiva Admin Investigation: B2C Order Dispute {order.order_id}"
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
                        <div style="background-color: #f57f17; padding: 20px; text-align: center; color: white;">
                            <h2 style="margin: 0; font-size: 22px;">Official Admin Communication</h2>
                        </div>
                        <div style="padding: 30px; color: #333;">
                            <p style="font-size: 15px; color: #555;">An update regarding the cancelled order <strong>{order.order_id}</strong>:</p>
                            <div style="background: #fff8e1; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #fbc02d;">
                                <p style="margin: 0; color: #333; font-size: 15px; font-style: italic;">"{custom_message}"</p>
                            </div>
                            <p style="font-size: 14px; color: #64748b;">Please reply directly to this email if you need to provide shipping receipts or evidence.</p>
                            <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Trust & Safety Team</p>
                        </div>
                    </div>
                </div>
                """
                vendor_email = order.product.listed_by.email if order.product else None
                recipients = [order.farmer.email]
                if vendor_email:
                    recipients.append(vendor_email)
                
                from django.utils.html import strip_tags
                from django.core.mail import send_mail
                send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', recipients, html_message=html_message, fail_silently=True)
                
                messages.success(request, "Investigation email successfully dispatched to involved parties.")
                return redirect('admin_b2c_refund_detail', order_id=order_id)

        context = {
            'order': order,
            'escrow': escrow,
            'farmer': order.farmer,
            'vendor': order.product.listed_by if order.product else None,
        }
        return render(request, 'admin_b2c_refund_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading B2C case details: {e}")
        return redirect('manage_b2c_refunds')


# --- UPGRADED: B2C FINANCIAL PROCESSOR ---
@login_required
def process_b2c_refund(request, order_id):
    if request.user.role != User.Role.ADMIN or request.method != 'POST':
        return redirect('index')

    try:
        order = get_object_or_404(InputOrder, order_id=order_id)
        action = request.POST.get('action')
        
        escrow = EscrowTransaction.objects.filter(security_token=f'ORDER-{order.order_id}').first()
        if not escrow:
            escrow = EscrowTransaction.objects.filter(
                purchaser=order.farmer, 
                item_purchased=order.product
            ).order_by('-created_at').first()

        from django.utils.html import strip_tags
        from django.core.mail import send_mail

        if action == 'refund':
            # 1. Process the money (if it exists)
            if escrow:
                escrow.payment_status = 'REFUNDED'
                escrow.save()
                messages.success(request, f"Refund authorized! ₹{escrow.amount_paid} returned to Farmer: {order.farmer.username}.")
            else:
                # Bypass for ghost orders to clear them safely
                messages.success(request, f"Ghost Order Resolved. No digital funds were attached.")

            # 2. PRO FIX: Change the ORDER STATUS so it is permanently deleted from the Admin Dashboard!
            order.status = 'REFUNDED'
            order.save()
            
            # --- BEAUTIFUL HTML EMAIL: FARMER CANCELLATION REFUND ---
            subject = f"Kultiva Update: Cancellation Refund Processed ({order.order_id})"
            html_message = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                    <div style="background-color: #f57f17; padding: 20px; text-align: center; color: white;">
                        <h2 style="margin: 0; font-size: 24px;">Order Cancellation & Refund</h2>
                    </div>
                    <div style="padding: 30px; color: #333;">
                        <p style="font-size: 16px;">Dear <strong>{order.farmer.username}</strong>,</p>
                        <p style="font-size: 15px; color: #555;">Your request to cancel the order for <strong>{order.product.title if order.product else 'Deleted Item'}</strong> has been securely processed by our administrators.</p>
                        
                        <div style="background: #fff8e1; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #fbc02d;">
                            <h3 style="margin: 0 0 10px 0; color: #1e293b;">Refund Summary</h3>
                            <p style="margin: 5px 0;"><strong>Order ID:</strong> {order.order_id}</p>
                            <p style="margin: 5px 0;"><strong>Total Refunded:</strong> <span style="color: #f57f17; font-size: 18px; font-weight: bold;">₹{escrow.amount_paid if escrow else '0.00'}</span></p>
                        </div>
                        
                        <p style="font-size: 14px; color: #64748b;">The funds will be credited back to your original payment method. We hope to serve you again soon!</p>
                        <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Administration</p>
                    </div>
                </div>
            </div>
            """
            send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', [order.farmer.email], html_message=html_message, fail_silently=True)

        elif action == 'release':
            if escrow:
                escrow.payment_status = 'COMPLETED'
                escrow.save()
            
            # 2. PRO FIX: Changing to DELIVERED permanently removes it from the Admin dashboard!
            order.status = 'DELIVERED' 
            order.save()
            
            vendor_name = order.product.listed_by.username if order.product else "Vendor"
            vendor_email = order.product.listed_by.email if order.product else None
            messages.success(request, f"Funds FORCE-RELEASED to Seller: {vendor_name}.")

            # --- BEAUTIFUL HTML EMAIL: SELLER FORCE RELEASE ---
            if vendor_email:
                subject = f"Kultiva Escrow: Dispute Resolved & Funds Released ({order.order_id})"
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                        <div style="background-color: #1b5e20; padding: 20px; text-align: center; color: white;">
                            <h2 style="margin: 0; font-size: 24px;">Funds Successfully Released</h2>
                        </div>
                        <div style="padding: 30px; color: #333;">
                            <p style="font-size: 16px;">Dear <strong>{vendor_name}</strong>,</p>
                            <p style="font-size: 15px; color: #555;">The Admin team has reviewed the cancellation dispute for order <strong>{order.order_id}</strong>. The dispute has been resolved in your favor.</p>
                            
                            <div style="background: #f1f8e9; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #2e7d32;">
                                <h3 style="margin: 0 0 10px 0; color: #1e293b;">Payment Released</h3>
                                <p style="margin: 5px 0;"><strong>Product:</strong> {order.product.title if order.product else 'Item'}</p>
                                <p style="margin: 5px 0;"><strong>Amount Transferred:</strong> <span style="color: #1b5e20; font-size: 18px; font-weight: bold;">₹{escrow.amount_paid if escrow else '0.00'}</span></p>
                            </div>
                            
                            <p style="font-size: 14px; color: #64748b;">The funds have been released from Escrow into your account. Thank you for maintaining high standards on our platform.</p>
                            <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Trust & Safety Team</p>
                        </div>
                    </div>
                </div>
                """
                send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', [vendor_email], html_message=html_message, fail_silently=True)

    except Exception as e:
        messages.error(request, f"Error processing B2C transaction: {e}")

    return redirect('manage_b2c_refunds')

# =========================================================
# --- ADMIN: GLOBAL MARKETPLACE MODERATION ---
# =========================================================

# --- 1. FARMER PRODUCTS (B2B HARVESTS) ---
@login_required
def manage_farmer_products(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        # Base Query: Fetch only products listed by Farmers (PRODUCE wing)
        products = MarketplaceListing.objects.filter(wing='PRODUCE').select_related('listed_by').order_by('-created_at')
        
        # PRO FIX: Apply the Status Filter dynamically!
        status_filter = request.GET.get('status', 'all')
        if status_filter in ['ACTIVE', 'OUT_OF_STOCK', 'HIDDEN', 'BANNED']:
            products = products.filter(status=status_filter)
        
        context = {
            'products': products,
            'current_status': status_filter, # Send this to the template to highlight the active tab
            'page_title': 'Farmer Harvest Listings',
            'theme_color': '#2e7d32' # Green for Farmers
        }
        return render(request, 'manage_farmer_products.html', context)
    except Exception as e:
        messages.error(request, f"Error loading Farmer Products: {e}")
        return redirect('admin_dashboard')

# --- 2. SELLER PRODUCTS (B2C INPUTS) ---
@login_required
def manage_seller_products(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        # Base Query: Fetch products listed by Input Sellers
        products = MarketplaceListing.objects.filter(wing='INPUT').select_related('listed_by').order_by('-created_at')
        
        # PRO FIX: Apply the Status Filter dynamically!
        status_filter = request.GET.get('status', 'all')
        if status_filter in ['ACTIVE', 'OUT_OF_STOCK', 'HIDDEN', 'BANNED']:
            products = products.filter(status=status_filter)
        
        context = {
            'products': products,
            'current_status': status_filter, # Send this to the template to highlight the active tab
            'page_title': 'Seller Input Listings',
            'theme_color': '#f57f17' # Orange/Yellow for Sellers
        }
        return render(request, 'manage_seller_products.html', context)
    except Exception as e:
        messages.error(request, f"Error loading Seller Products: {e}")
        return redirect('admin_dashboard')


# --- 3. DEDICATED PRODUCT INVESTIGATION DASHBOARD ---
@login_required
def admin_product_detail(request, product_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        product = get_object_or_404(MarketplaceListing, id=product_id)

        # Handle Custom Warning/Investigation Emails
        if request.method == 'POST' and request.POST.get('action') == 'send_warning_email':
            custom_message = request.POST.get('custom_message', '').strip()
            if custom_message:
                from django.utils.html import strip_tags
                from django.core.mail import send_mail
                
                subject = f"Kultiva Admin Notice: Regarding your listing '{product.title}'"
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
                        <div style="background-color: #0288d1; padding: 20px; text-align: center; color: white;">
                            <h2 style="margin: 0; font-size: 22px;">Listing Under Review</h2>
                        </div>
                        <div style="padding: 30px; color: #333;">
                            <p style="font-size: 15px; color: #555;">Dear <strong>{product.listed_by.username}</strong>,</p>
                            <p style="font-size: 15px; color: #555;">Our Admin team is currently reviewing your marketplace listing for <strong>{product.title}</strong>.</p>
                            
                            <div style="background: #e1f5fe; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #0288d1;">
                                <p style="margin: 0; color: #01579b; font-size: 15px; font-style: italic;">"{custom_message}"</p>
                            </div>
                            
                            <p style="font-size: 14px; color: #64748b;">Please log in to your account and update your listing to comply with our platform policies to avoid a permanent takedown.</p>
                            <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Moderation Team</p>
                        </div>
                    </div>
                </div>
                """
                send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', [product.listed_by.email], html_message=html_message, fail_silently=True)
                
                messages.success(request, f"Warning email successfully dispatched to {product.listed_by.username}.")
                return redirect('admin_product_detail', product_id=product.id)

        context = {
            'product': product,
            'seller': product.listed_by,
        }
        return render(request, 'admin_product_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading product details: {e}")
        return redirect('admin_dashboard')


# --- 4. THE UNIVERSAL TAKEDOWN ACTION ---
@login_required
def takedown_product(request, product_id):
    if request.user.role != User.Role.ADMIN or request.method != 'POST':
        return redirect('index')

    try:
        product = get_object_or_404(MarketplaceListing, id=product_id)
        
        # Save details before deletion for the email and redirect logic
        wing = product.wing
        seller_email = product.listed_by.email
        seller_name = product.listed_by.username
        product_title = product.title
        
        takedown_reason = request.POST.get('takedown_reason', 'Violation of Kultiva Marketplace Terms & Conditions.')

        from django.utils.html import strip_tags
        from django.core.mail import send_mail

        # --- BEAUTIFUL HTML EMAIL: PERMANENT TAKEDOWN NOTICE ---
        subject = f"Kultiva Moderation: Listing Removed ({product_title})"
        html_message = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                <div style="background-color: #d32f2f; padding: 20px; text-align: center; color: white;">
                    <h2 style="margin: 0; font-size: 24px;">Marketplace Listing Removed</h2>
                </div>
                <div style="padding: 30px; color: #333;">
                    <p style="font-size: 16px;">Dear <strong>{seller_name}</strong>,</p>
                    <p style="font-size: 15px; color: #555;">This is an official notice that your listing for <strong>{product_title}</strong> has been permanently removed from the Kultiva platform by our Moderation Team.</p>
                    
                    <div style="background: #ffebee; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #c62828;">
                        <h3 style="margin: 0 0 10px 0; color: #b71c1c;">Reason for Takedown:</h3>
                        <p style="margin: 0; color: #c62828; font-size: 15px;">{takedown_reason}</p>
                    </div>
                    
                    <p style="font-size: 14px; color: #64748b;">Repeated violations of our marketplace policies may result in account suspension. If you believe this was an error, please contact support.</p>
                    <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Trust & Safety Team</p>
                </div>
            </div>
        </div>
        """
        send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', [seller_email], html_message=html_message, fail_silently=True)

        # Perform the actual physical deletion from the database
        product.status = 'BANNED'
        product.save()
        messages.success(request, f"Successfully executed TAKEDOWN on '{product_title}'. The user has been notified.")

        # Smart Redirect: Send the Admin back to the correct dashboard based on what they deleted!
        if wing == 'PRODUCE':
            return redirect('manage_farmer_products')
        else:
            return redirect('manage_seller_products')

    except Exception as e:
        messages.error(request, f"Error processing product takedown: {e}")
        return redirect('admin_dashboard')

# =========================================================
# --- ADMIN: GLOBAL ORDER LEDGERS (WITH ADVANCED FILTERS) ---
# =========================================================

# --- 1. SELLER ORDERS (B2C: Seeds & Tools) ---
@login_required
def manage_seller_orders(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        orders = InputOrder.objects.select_related('farmer', 'product__listed_by').order_by('-created_at')
        
        # 1. Apply Search Filter
        query = request.GET.get('q', '').strip()
        if query:
            from django.db.models import Q
            orders = orders.filter(
                Q(order_id__icontains=query) |
                Q(farmer__username__icontains=query) |
                Q(product__title__icontains=query)
            )

        # 2. Apply Tab Status Filter
        status_filter = request.GET.get('status', 'all')
        if status_filter == 'pending':
            orders = orders.filter(status='PENDING')
        elif status_filter == 'transit':
            orders = orders.filter(status='SHIPPED')
        elif status_filter == 'delivered':
            orders = orders.filter(status='DELIVERED')
        elif status_filter == 'refunded':
            orders = orders.filter(status='REFUNDED')
        elif status_filter == 'cancelled':
            orders = orders.filter(status='CANCELLED')

        context = {
            'orders': orders,
            'current_status': status_filter,
            'search_query': query,
            'page_title': 'B2C Retail Orders Ledger',
            'theme_color': '#f57f17' # Orange Theme for Sellers
        }
        return render(request, 'manage_seller_orders.html', context)
    except Exception as e:
        messages.error(request, f"Error loading Seller Orders: {e}")
        return redirect('admin_dashboard')


# --- 2. BUYER ORDERS (B2B: Corporate Harvests) ---
@login_required
def manage_buyer_orders(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        orders = DirectTradeProposal.objects.select_related('farmer', 'buyer', 'listing').order_by('-created_at')
        
        # 1. Apply Search Filter
        query = request.GET.get('q', '').strip()
        if query:
            from django.db.models import Q
            orders = orders.filter(
                Q(listing__title__icontains=query) |
                Q(farmer__username__icontains=query) |
                Q(buyer__username__icontains=query)
            )

        # 2. Apply Tab Status Filter mapped to DirectTradeProposal model
        status_filter = request.GET.get('status', 'all')
        if status_filter == 'pending':
            orders = orders.filter(status='PENDING')
        elif status_filter == 'accepted':
            orders = orders.filter(status='ACCEPTED')
        elif status_filter == 'rejected':
            orders = orders.filter(status='REJECTED')
        elif status_filter == 'completed':
            orders = orders.filter(status='COMPLETED')  
        elif status_filter == 'cancelled':
            orders = orders.filter(status='CANCELLED')

        context = {
            'orders': orders,
            'current_status': status_filter,
            'search_query': query,
            'page_title': 'B2B Corporate Orders Ledger',
            'theme_color': '#1565c0' # Blue Theme for Corporate Buyers
        }
        return render(request, 'manage_buyer_orders.html', context)
    except Exception as e:
        messages.error(request, f"Error loading Buyer Orders: {e}")
        return redirect('admin_dashboard')

# --- 3. B2C ORDER INVESTIGATION DASHBOARD ---
@login_required
def admin_seller_order_detail(request, order_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        order = get_object_or_404(InputOrder, order_id=order_id)
        
        # Look up if there is an escrow vault attached to this order
        escrow = EscrowTransaction.objects.filter(security_token=f'ORDER-{order.order_id}').first()
        if not escrow:
            escrow = EscrowTransaction.objects.filter(purchaser=order.farmer, item_purchased=order.product).order_by('-created_at').first()

        # Handle Official Logistics/Support Emails
        if request.method == 'POST' and request.POST.get('action') == 'send_order_email':
            custom_message = request.POST.get('custom_message', '').strip()
            recipient_type = request.POST.get('recipient_type') # 'farmer' or 'seller' or 'both'
            
            if custom_message:
                from django.utils.html import strip_tags
                from django.core.mail import send_mail
                
                subject = f"Kultiva Admin Support: Regarding Order {order.order_id}"
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
                        <div style="background-color: #f57f17; padding: 20px; text-align: center; color: white;">
                            <h2 style="margin: 0; font-size: 22px;">Official Order Communication</h2>
                        </div>
                        <div style="padding: 30px; color: #333;">
                            <p style="font-size: 15px; color: #555;">An update regarding B2C Order <strong>{order.order_id}</strong>:</p>
                            <div style="background: #fff8e1; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #fbc02d;">
                                <p style="margin: 0; color: #333; font-size: 15px; font-style: italic;">"{custom_message}"</p>
                            </div>
                            <p style="font-size: 14px; color: #64748b;">Please reply directly to this email if you need to provide shipping receipts or further assistance.</p>
                            <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Logistics Team</p>
                        </div>
                    </div>
                </div>
                """
                
                recipients = []
                if recipient_type in ['farmer', 'both']:
                    recipients.append(order.farmer.email)
                if recipient_type in ['seller', 'both'] and order.product and order.product.listed_by:
                    recipients.append(order.product.listed_by.email)
                
                if recipients:
                    send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', recipients, html_message=html_message, fail_silently=True)
                    messages.success(request, f"Support email successfully dispatched to selected parties.")
                
                return redirect('admin_seller_order_detail', order_id=order.order_id)

        context = {
            'order': order,
            'escrow': escrow,
        }
        return render(request, 'admin_seller_order_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading B2C order details: {e}")
        return redirect('manage_seller_orders')


# --- 4. B2B ORDER INVESTIGATION DASHBOARD ---
@login_required
def admin_buyer_order_detail(request, proposal_id):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        proposal = get_object_or_404(DirectTradeProposal, id=proposal_id)
        
        # Handle Official Logistics/Support Emails
        if request.method == 'POST' and request.POST.get('action') == 'send_order_email':
            custom_message = request.POST.get('custom_message', '').strip()
            recipient_type = request.POST.get('recipient_type') # 'farmer' or 'buyer' or 'both'
            
            if custom_message:
                from django.utils.html import strip_tags
                from django.core.mail import send_mail
                
                subject = f"Kultiva Admin Support: Regarding B2B Trade #{proposal.id}"
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; background-color: #f8fafc;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
                        <div style="background-color: #1565c0; padding: 20px; text-align: center; color: white;">
                            <h2 style="margin: 0; font-size: 22px;">Official Trade Communication</h2>
                        </div>
                        <div style="padding: 30px; color: #333;">
                            <p style="font-size: 15px; color: #555;">An update regarding your B2B Harvest Trade:</p>
                            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #1565c0;">
                                <p style="margin: 0; color: #333; font-size: 15px; font-style: italic;">"{custom_message}"</p>
                            </div>
                            <p style="font-size: 14px; color: #64748b;">Please reply directly to this email if you need to provide logistics updates or dispatch proofs.</p>
                            <p style="margin-top: 30px; font-weight: bold; color: #1b5e20;">The Kultiva Trade Desk</p>
                        </div>
                    </div>
                </div>
                """
                
                recipients = []
                if recipient_type in ['farmer', 'both']:
                    recipients.append(proposal.farmer.email)
                if recipient_type in ['buyer', 'both']:
                    recipients.append(proposal.buyer.email)
                
                if recipients:
                    send_mail(subject, strip_tags(html_message), 'admin@kultiva.com', recipients, html_message=html_message, fail_silently=True)
                    messages.success(request, f"Trade support email successfully dispatched.")
                
                return redirect('admin_buyer_order_detail', proposal_id=proposal.id)

        context = {
            'proposal': proposal,
        }
        return render(request, 'admin_buyer_order_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading B2B trade details: {e}")
        return redirect('manage_buyer_orders')
    
# =========================================================
# --- ADMIN: ENTERPRISE ANALYTICS & REPORTS ---
# =========================================================

# --- 1. FARMER & B2B HARVEST ANALYTICS ---
@login_required
def admin_farmer_report(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        filter_type = request.GET.get('time_filter', 'month')
        now = timezone.now()
        
        if filter_type == 'day':
            start_date = now - timedelta(days=30)
            trunc_func = TruncDay
            date_format = "%d %b"
        elif filter_type == 'week':
            start_date = now - timedelta(weeks=12)
            trunc_func = TruncWeek
            date_format = "W%V %Y"
        elif filter_type == 'year':
            start_date = now - timedelta(days=365*5)
            trunc_func = TruncYear
            date_format = "%Y"
        else:
            start_date = now - timedelta(days=365)
            trunc_func = TruncMonth
            date_format = "%b %Y"

        total_farmers = User.objects.filter(role='FARMER').count()
        total_harvests = MarketplaceListing.objects.filter(wing='PRODUCE').count()
        all_completed_trades = DirectTradeProposal.objects.filter(status='COMPLETED').select_related('listing')
        
        # PRO FIX: Crash-proof Revenue Calculation using getattr!
        total_b2b_revenue = 0
        for trade in all_completed_trades:
            # If quantity/proposed_price don't exist in your models.py, it defaults to 1 and listing.price safely
            qty = getattr(trade, 'quantity', 1)
            price = getattr(trade, 'proposed_price', getattr(trade.listing, 'price', 0) if trade.listing else 0)
            total_b2b_revenue += float(qty) * float(price)

        farmer_growth = User.objects.filter(role='FARMER', date_joined__gte=start_date) \
            .annotate(period=trunc_func('date_joined')) \
            .values('period') \
            .annotate(count=Count('user_id')) \
            .order_by('period')
        
        fg_labels = [entry['period'].strftime(date_format) for entry in farmer_growth]
        fg_data = [entry['count'] for entry in farmer_growth]

        completed_trades_qs = DirectTradeProposal.objects.filter(status='COMPLETED', created_at__gte=start_date) \
            .annotate(period=trunc_func('created_at')) \
            .order_by('period')
            
        revenue_dict = {}
        for trade in completed_trades_qs:
            if trade.period:
                p_label = trade.period.strftime(date_format)
                qty = getattr(trade, 'quantity', 1)
                price = getattr(trade, 'proposed_price', getattr(trade.listing, 'price', 0) if trade.listing else 0)
                revenue_dict[p_label] = revenue_dict.get(p_label, 0) + (float(qty) * float(price))

        tv_labels = list(revenue_dict.keys())
        tv_data = list(revenue_dict.values())

        categories = MarketplaceListing.objects.filter(wing='PRODUCE').values('category').annotate(count=Count('id'))
        cat_dict = dict(MarketplaceListing.CATEGORY_CHOICES)
        cat_labels = [cat_dict.get(entry['category'], entry['category']) for entry in categories]
        cat_data = [entry['count'] for entry in categories]

        # NEW: Fetching the detailed list for the Data Table!
        farmers_list = User.objects.filter(role='FARMER').select_related('farmer_profile').order_by('-date_joined')

        context = {
            'page_title': 'Farmer Analytics & Registry Report',
            'theme_color': '#2e7d32',
            'filter_type': filter_type,
            'total_farmers': total_farmers,
            'total_harvests': total_harvests,
            'total_trades': all_completed_trades.count(),
            'total_b2b_revenue': total_b2b_revenue,
            'farmers_list': farmers_list, # Added to context
            'fg_labels': json.dumps(fg_labels),
            'fg_data': json.dumps(fg_data),
            'tv_labels': json.dumps(tv_labels),
            'tv_data': json.dumps(tv_data),
            'cat_labels': json.dumps(cat_labels),
            'cat_data': json.dumps(cat_data),
        }
        return render(request, 'admin_farmer_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating Farmer report: {e}")
        return redirect('admin_dashboard')
    
# --- 2. SELLER & B2C RETAIL ANALYTICS ---
@login_required
def admin_seller_report(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        # 1. TIME FILTER LOGIC
        filter_type = request.GET.get('time_filter', 'month')
        now = timezone.now()
        
        if filter_type == 'day':
            start_date = now - timedelta(days=30)
            trunc_func = TruncDay
            date_format = "%d %b"
        elif filter_type == 'week':
            start_date = now - timedelta(weeks=12)
            trunc_func = TruncWeek
            date_format = "W%V %Y"
        elif filter_type == 'year':
            start_date = now - timedelta(days=365*5)
            trunc_func = TruncYear
            date_format = "%Y"
        else:
            start_date = now - timedelta(days=365)
            trunc_func = TruncMonth
            date_format = "%b %Y"

        # 2. LIFETIME METRICS
        total_sellers = User.objects.filter(role='SELLER').count()
        total_inputs = MarketplaceListing.objects.filter(wing='INPUT').count()
        successful_orders = InputOrder.objects.filter(status='DELIVERED')
        total_b2c_revenue = successful_orders.aggregate(total=Sum('total_amount'))['total'] or 0

        # 3. CHART DATA
        seller_growth = User.objects.filter(role='SELLER', date_joined__gte=start_date) \
            .annotate(period=trunc_func('date_joined')) \
            .values('period') \
            .annotate(count=Count('user_id')) \
            .order_by('period')
        
        sg_labels = [entry['period'].strftime(date_format) for entry in seller_growth]
        sg_data = [entry['count'] for entry in seller_growth]

        revenue_volume = InputOrder.objects.filter(status='DELIVERED', created_at__gte=start_date) \
            .annotate(period=trunc_func('created_at')) \
            .values('period') \
            .annotate(revenue=Sum('total_amount')) \
            .order_by('period')

        rv_labels = [entry['period'].strftime(date_format) for entry in revenue_volume]
        rv_data = [float(entry['revenue'] or 0) for entry in revenue_volume]

        categories = MarketplaceListing.objects.filter(wing='INPUT').values('category').annotate(count=Count('id'))
        cat_dict = dict(MarketplaceListing.CATEGORY_CHOICES)
        cat_labels = [cat_dict.get(entry['category'], entry['category']) for entry in categories]
        cat_data = [entry['count'] for entry in categories]

        # NEW: Fetching the detailed list for the Retail Registry Log
        sellers_list = User.objects.filter(role='SELLER').select_related('seller_profile').order_by('-date_joined')

        context = {
            'page_title': 'Seller Analytics & Retail Registry',
            'theme_color': '#f57f17', 
            'filter_type': filter_type,
            'total_sellers': total_sellers,
            'total_inputs': total_inputs,
            'total_orders': successful_orders.count(),
            'total_b2c_revenue': total_b2c_revenue,
            'sellers_list': sellers_list, # Added to context
            'sg_labels': json.dumps(sg_labels),
            'sg_data': json.dumps(sg_data),
            'rv_labels': json.dumps(rv_labels),
            'rv_data': json.dumps(rv_data),
            'cat_labels': json.dumps(cat_labels),
            'cat_data': json.dumps(cat_data),
        }
        return render(request, 'admin_seller_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating Seller report: {e}")
        return redirect('admin_dashboard')

# --- 3. BUYER & CORPORATE TRADE ANALYTICS ---
@login_required
def admin_buyer_report(request):
    if request.user.role != User.Role.ADMIN:
        messages.error(request, "Access Denied.")
        return redirect('index')

    try:
        filter_type = request.GET.get('time_filter', 'month')
        now = timezone.now()
        
        if filter_type == 'day':
            start_date = now - timedelta(days=30)
            trunc_func = TruncDay
            date_format = "%d %b"
        elif filter_type == 'week':
            start_date = now - timedelta(weeks=12)
            trunc_func = TruncWeek
            date_format = "W%V %Y"
        elif filter_type == 'year':
            start_date = now - timedelta(days=365*5)
            trunc_func = TruncYear
            date_format = "%Y"
        else:
            start_date = now - timedelta(days=365)
            trunc_func = TruncMonth
            date_format = "%b %Y"

        total_buyers = User.objects.filter(role='BUYER').count()
        total_proposals = DirectTradeProposal.objects.all().count()
        all_completed_trades = DirectTradeProposal.objects.filter(status='COMPLETED').select_related('listing')
        
        # PRO FIX: Crash-proof Capital deployed calculation
        total_capital_deployed = 0
        for trade in all_completed_trades:
            qty = getattr(trade, 'quantity', 1)
            price = getattr(trade, 'proposed_price', getattr(trade.listing, 'price', 0) if trade.listing else 0)
            total_capital_deployed += float(qty) * float(price)

        buyer_growth = User.objects.filter(role='BUYER', date_joined__gte=start_date) \
            .annotate(period=trunc_func('date_joined')) \
            .values('period') \
            .annotate(count=Count('user_id')) \
            .order_by('period')
        
        bg_labels = [entry['period'].strftime(date_format) for entry in buyer_growth]
        bg_data = [entry['count'] for entry in buyer_growth]

        completed_trades_qs = DirectTradeProposal.objects.filter(status='COMPLETED', created_at__gte=start_date) \
            .annotate(period=trunc_func('created_at')) \
            .order_by('period')
            
        revenue_dict = {}
        for trade in completed_trades_qs:
            if trade.period:
                p_label = trade.period.strftime(date_format)
                qty = getattr(trade, 'quantity', 1)
                price = getattr(trade, 'proposed_price', getattr(trade.listing, 'price', 0) if trade.listing else 0)
                revenue_dict[p_label] = revenue_dict.get(p_label, 0) + (float(qty) * float(price))

        cv_labels = list(revenue_dict.keys())
        cv_data = list(revenue_dict.values())

        statuses = DirectTradeProposal.objects.values('status').annotate(count=Count('id'))
        status_labels = [entry['status'].title() for entry in statuses]
        status_data = [entry['count'] for entry in statuses]

        # NEW: Fetching the detailed list for the Corporate Data Table!
        buyers_list = User.objects.filter(role='BUYER').select_related('buyer_profile').order_by('-date_joined')

        context = {
            'page_title': 'Corporate Buyer Analytics & Registry',
            'theme_color': '#1565c0',
            'filter_type': filter_type,
            'total_buyers': total_buyers,
            'total_proposals': total_proposals,
            'completed_trades_count': all_completed_trades.count(),
            'total_capital_deployed': total_capital_deployed,
            'buyers_list': buyers_list, # Added to context
            'bg_labels': json.dumps(bg_labels),
            'bg_data': json.dumps(bg_data),
            'cv_labels': json.dumps(cv_labels),
            'cv_data': json.dumps(cv_data),
            'status_labels': json.dumps(status_labels),
            'status_data': json.dumps(status_data),
        }
        return render(request, 'admin_buyer_report.html', context)
        
    except Exception as e:
        messages.error(request, f"Error generating Buyer report: {e}")
        return redirect('admin_dashboard')
    
# =========================================================
# --- API: PINCODE AUTO-FILL (DECOUPLED UX) ---
# =========================================================
def pincode_lookup_api(request, pincode):
    """
    Invisible API endpoint for frontend Pincode auto-filling.
    Reads from the standalone PincodeDirectory table.
    """
    try:
        from .models import PincodeDirectory # Import here to avoid circular logic
        
        # Look up the pincode in our standalone dictionary
        location = PincodeDirectory.objects.get(pincode=pincode)
        
        return JsonResponse({
            'success': True,
            'district': location.district,
            'state': location.state
        })
    except PincodeDirectory.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Pincode not found in directory.'
        })