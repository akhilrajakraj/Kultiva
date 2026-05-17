from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

# 1. USERS TABLE [cite: 869-873]
class User(AbstractUser):
    class Role(models.TextChoices):
        FARMER = 'FARMER', 'Farmer'
        BUYER = 'BUYER', 'Buyer'
        SELLER = 'SELLER', 'Seller'
        ADMIN = 'ADMIN', 'Admin'

    user_id = models.AutoField(primary_key=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FARMER)
    is_verified = models.BooleanField(default=False)
    # date_joined is inherited from AbstractUser

# 2. ADDRESSES TABLE [cite: 878-883]
class Address(models.Model):
    addr_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    village = models.CharField(max_length=50)
    district = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=6)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

# 3. FARMER PROFILES TABLE [cite: 887-892]
class FarmerProfile(models.Model):
    fp_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    aadhar_no = models.CharField(max_length=12, unique=True)
    kissan_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    land_area = models.FloatField()
    soil_type = models.CharField(max_length=20)
    irrigation = models.CharField(max_length=20)

# 4. BUYER PROFILES TABLE [cite: 896-901]
class BuyerProfile(models.Model):
    bp_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyer_profile')
    company_name = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=15, unique=True)
    iec_code = models.CharField(max_length=10)
    apeda_org = models.CharField(max_length=20, null=True, blank=True)

# 5. SELLER PROFILES TABLE [cite: 905-909]
class SellerProfile(models.Model):
    sp_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_profile')
    shop_name = models.CharField(max_length=100)
    # Renamed 'license_no' to 'license_number' to match view
    license_number = models.CharField(max_length=50, unique=True) 
    # Added these fields to match the form
    gst_number = models.CharField(max_length=15, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
# 6. WEATHER HISTORY (The Fallback Database)
class WeatherHistory(models.Model):
    district = models.CharField(max_length=50)
    month = models.IntegerField() # 1 (Jan) to 12 (Dec)
    avg_temp = models.FloatField() # In Celsius
    avg_humidity = models.FloatField() # Percentage
    avg_rainfall = models.FloatField() # In mm

    class Meta:
        # This ensures we don't accidentally create two 'July' entries for 'Alappuzha'
        unique_together = ('district', 'month') 

    def __str__(self):
        return f"{self.district} - Month {self.month}"
    
# 7. UNIFIED MARKETPLACE TABLE
class MarketplaceListing(models.Model):
    listed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    
    WING_CHOICES = (
        ('PRODUCE', 'Farm Produce (Harvest)'),
        ('INPUT', 'Farming Input (Tools/Seeds/Fertilizers)')
    )
    wing = models.CharField(max_length=15, choices=WING_CHOICES)

    CATEGORY_CHOICES = (
        ('GRAINS', 'Grains & Cereals'),
        ('VEGETABLES', 'Vegetables'),
        ('FRUITS', 'Fruits'),
        ('CASH_CROPS', 'Cash Crops (Cotton, Sugarcane)'), 
        ('SPICES', 'Spices & Condiments'),
        ('SEEDS', 'Seeds'),
        ('FERTILIZERS', 'Fertilizers & Nutrients'),
        ('AGROCHEMICALS', 'Pesticides & Herbicides'),
        ('TOOLS', 'Farming Tools'),
        ('MACHINERY', 'Heavy Machinery & Parts'),
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    title = models.CharField(max_length=100)
    variety_or_brand = models.CharField(max_length=100, null=True, blank=True) 
    description = models.TextField(help_text="Detailed description.")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=20) 
    available_stock = models.FloatField()
    image = models.ImageField(upload_to='market_images/', null=True, blank=True)
    
    STATUS_CHOICES = (
        ('ACTIVE', 'Active & In Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('HIDDEN', 'Hidden by Seller'),
        ('BANNED', 'Removed by Admin')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    # --- NEW ADDITIONS FOR INDUSTRY STANDARD EXPERIENCE ---
    min_order_quantity = models.FloatField(default=1, help_text="Minimum amount buyer must purchase")
    harvest_date = models.DateField(null=True, blank=True, help_text="Required for Produce")
    is_organic = models.BooleanField(default=False, help_text="Is this certified organic?")
    grade = models.CharField(max_length=50, null=True, blank=True)
    
    # The Magic Field: Stores crop-specific data (Moisture, Shelf-life, etc)
    specifications = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.title} ({self.wing})"
    
# 8. GEOSPATIAL SOIL GRIDS (Smart Mapping)
class GridSoilData(models.Model):
    # 1. Spatial Identifiers (The 1km x 1km grid center)
    grid_lat = models.FloatField(help_text="Latitude (2 decimals)")
    grid_lon = models.FloatField(help_text="Longitude (2 decimals)")
    
    # 2. Physical Parameters
    ph = models.FloatField(help_text="pH level")
    ec = models.FloatField(help_text="Electrical Conductivity")
    oc = models.FloatField(help_text="Organic Carbon (%)")
    
    # 3. Macro Nutrients (kg/ha)
    avg_n = models.FloatField(help_text="Nitrogen (N)")
    avg_p = models.FloatField(help_text="Phosphorus (P)")
    avg_k = models.FloatField(help_text="Potassium (K)")
    avg_s = models.FloatField(help_text="Sulphur (S)")
    
    # 4. Micro Nutrients (ppm)
    avg_zn = models.FloatField(help_text="Zinc (Zn)")
    avg_fe = models.FloatField(help_text="Iron (Fe)")
    avg_cu = models.FloatField(help_text="Copper (Cu)")
    avg_mn = models.FloatField(help_text="Manganese (Mn)")
    avg_b = models.FloatField(help_text="Boron (B)")

    # 5. Pre-computed Advisory (The AI/Expert System Output)
    recommendation_text = models.TextField(help_text="Rule-based SHC Advisory", blank=True, null=True)

    class Meta:
        # Ensures we don't map the exact same GPS block twice
        unique_together = ('grid_lat', 'grid_lon')

    def __str__(self):
        return f"Grid [{self.grid_lat}, {self.grid_lon}] - pH: {self.ph}"
    
# 9. MANUAL SOIL REPORTS (For Farmers outside the Grid)
# 9. MANUAL SOIL REPORTS (For Farmers outside the Grid)
class ManualSoilReport(models.Model):
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manual_soil_reports')
    
    # ==============================================================================
    # 🔬 THE FIX: MULTI-FARM LOCATION LINK
    # ==============================================================================
    # Links directly to Table #2 (Address). We use SET_NULL so if an address 
    # is deleted, the historical lab report data isn't destroyed.
    farm_address = models.ForeignKey('Address', on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_reports')

    STATUS_CHOICES = (
        ('PENDING', 'Pending Lab Test'),
        ('COMPLETED', 'Test Completed / Data Uploaded')
    )
    request_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    request_date = models.DateTimeField(auto_now_add=True)

    # 🔬 ARCHITECTURE NOTE: 'land_area' has been REMOVED as requested.
    previous_crop = models.CharField(max_length=100, help_text="Crop harvested last season", null=True, blank=True)

    # --- THE FIX: Secure Storage for the PDF/Image Upload ---
    report_file = models.FileField(upload_to='soil_reports/', null=True, blank=True)

    # The Custom Data
    n = models.FloatField(null=True, blank=True)
    p = models.FloatField(null=True, blank=True)
    k = models.FloatField(null=True, blank=True)
    ph = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Manual Report for {self.farmer.username} - {self.request_status}"

# 10. DIRECT TRADE PROPOSALS (Junction Table for Farmer -> Buyer Bids)
class DirectTradeProposal(models.Model):
    listing = models.ForeignKey(MarketplaceListing, on_delete=models.CASCADE, related_name='trade_proposals')
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_proposals')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_proposals')
    
    # Negotiation Status
    STATUS_CHOICES = (
        ('PENDING', 'Pending Buyer Approval'),
        ('ACCEPTED', 'Accepted - QR Pending'),
        ('REJECTED', 'Rejected by Buyer'),
        ('CANCELLED', 'Cancelled by Farmer'),
        ('COMPLETED', 'Completed Trade') # Added to align with views
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Trade specifics
    message = models.TextField(blank=True, null=True, help_text="Custom message to the buyer")
    
    # --- NEW: Explicit Math Fields for B2B Negotiations ---
    requested_quantity = models.FloatField(default=1.0, help_text="Amount the buyer actually wants to buy")
    proposed_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Custom negotiated price per unit")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Total value of the negotiated deal")
    
    # --- SECURITY & ESCROW LOGIC ---
    security_token = models.CharField(max_length=100, blank=True, null=True, help_text="Unique cryptographic token for QR")
    qr_code = models.ImageField(upload_to='trade_qrs/', null=True, blank=True)
    is_paid = models.BooleanField(default=False, help_text="Has the escrow payment been released?")
    scheduled_pickup_date = models.DateTimeField(null=True, blank=True, help_text="When the buyer's truck will arrive")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Proposal: {self.listing.title} -> {self.buyer.username} ({self.status})"

# 11. UNIVERSAL ORDER / ESCROW TRANSACTION TABLE
class EscrowTransaction(models.Model):
    # Unique order receipt number (e.g., TXN-A1B2C3D4)
    transaction_id = models.CharField(max_length=100, unique=True, editable=False)
    
    # What was bought? (Links to the unified marketplace table)
    item_purchased = models.ForeignKey(MarketplaceListing, on_delete=models.SET_NULL, null=True)
    
    # Who gets the money? (Could be Farmer or Seller)
    vendor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales_received')
    
    # Who pays the money? (Could be Buyer or Farmer)
    purchaser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases_made')
    
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    
    PAYMENT_STATUS_CHOICES = (
        ('ESCROW_LOCKED', 'Funds Locked in Escrow'),
        ('COMPLETED', 'Payment Released to Vendor'),
        ('REFUNDED', 'Payment Refunded')
    )
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='COMPLETED')
    
    # Link to the cryptographic token that authorized this
    security_token = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            # Auto-generate a cool transaction ID
            import uuid
            self.transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_id} | {self.purchaser.username} -> {self.vendor.username} (₹{self.amount_paid})"

# 12. INPUT MARKETPLACE ORDERS (Standard E-Commerce B2C)
class InputOrder(models.Model):
    order_id = models.CharField(max_length=50, unique=True, editable=False)
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='input_orders')
    product = models.ForeignKey(MarketplaceListing, on_delete=models.SET_NULL, null=True)
    
    quantity = models.FloatField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    PAYMENT_CHOICES = (
        ('UPI', 'UPI Payment'),
        ('CARD', 'Credit/Debit Card'),
        ('COD', 'Cash on Delivery')
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    
    STATUS_CHOICES = (
        ('PENDING', 'Order Placed & Pending'),
        ('SHIPPED', 'Shipped by Seller'),
        ('DELIVERED', 'Delivered successfully'),
        ('CANCELLED', 'Order Cancelled')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    delivery_address = models.TextField(help_text="Snapshot of address at time of order")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.order_id:
            import uuid
            self.order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_id} - {self.farmer.username}"

from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

# 13. UNIFIED TRUST ECOSYSTEM (The Universal Feedback Table)
class UnifiedReview(models.Model):
    # 1. The Core Network Links
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_written')
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')

    # 2. The Feedback Data
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], help_text="1 to 5 Stars")
    comment = models.TextField(blank=True, null=True)
    
    # --- NEW: SECURE IMAGE UPLOAD FIELD ---
    image = models.ImageField(upload_to='review_images/', null=True, blank=True)

    # 3. The Proof of Transaction (Nullable, because it will only link to ONE of these)
    # We use strings for model names to avoid circular import issues
    input_order = models.OneToOneField('InputOrder', on_delete=models.CASCADE, null=True, blank=True, related_name='review')
    b2b_trade = models.OneToOneField('DirectTradeProposal', on_delete=models.CASCADE, null=True, blank=True, related_name='review')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    # --- THE SENIOR DEVELOPER MAGIC: Data Integrity Check ---
    def clean(self):
        super().clean()
        # Ensure the review is linked to EXACTLY one transaction type
        if self.input_order and self.b2b_trade:
            raise ValidationError("A review cannot be linked to both an Input Order and a B2B Trade simultaneously.")
        if not self.input_order and not self.b2b_trade:
            raise ValidationError("A review must be linked to a valid transaction to prevent spam.")

    def save(self, *args, **kwargs):
        self.full_clean() # Forces the clean() method to run before saving to the database
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reviewer.username} rated {self.reviewee.username} ({self.rating}/5)"

# --- STANDALONE POSTAL DICTIONARY (For Frontend Auto-fill API) ---
class PincodeDirectory(models.Model):
    pincode = models.CharField(max_length=6, primary_key=True)
    district = models.CharField(max_length=50)
    state = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.pincode} -> {self.district}"