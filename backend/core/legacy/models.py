"""Legacy model compatibility exports.

Do not duplicate Django model classes here. Importing the canonical models keeps
existing migration/table ownership intact while domain extraction is performed.
"""
from Kultiva.models import (
    User, Address, FarmerProfile, BuyerProfile, SellerProfile,
    WeatherHistory, MarketplaceListing, GridSoilData, ManualSoilReport,
    DirectTradeProposal, EscrowTransaction, InputOrder, UnifiedReview,
    PincodeDirectory,
)

__all__ = [name for name in globals() if not name.startswith('_')]
