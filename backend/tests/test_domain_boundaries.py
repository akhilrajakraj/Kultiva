import os
import unittest

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Kultiva.settings')

import django

django.setup()

from backend.apps.accounts.models import User, Address
from backend.apps.farmers.models import FarmerProfile, ManualSoilReport
from backend.apps.buyers.models import BuyerProfile, DirectTradeProposal
from backend.apps.sellers.models import SellerProfile
from backend.apps.marketplace.models import MarketplaceListing
from backend.apps.orders.models import InputOrder
from backend.apps.payments.models import EscrowTransaction
from backend.apps.escrow.models import EscrowTransaction as EscrowTransactionFromEscrow
from backend.apps.soil.models import GridSoilData
from backend.apps.weather.models import WeatherHistory
from backend.apps.reviews.models import UnifiedReview
from backend.ai.crop_prediction.service import predict_best_crop
from backend.ai.soil_analysis.service import get_safe_defaults
from backend.ai.weather_intelligence.service import IndianAgriGeocoder
from backend.apps.advisory.services import get_crop_advisory


class DomainBoundaryTests(unittest.TestCase):
    def test_account_boundary_exports_canonical_models(self):
        from Kultiva.models import User as LegacyUser, Address as LegacyAddress
        self.assertIs(User, LegacyUser)
        self.assertIs(Address, LegacyAddress)

    def test_business_boundaries_export_canonical_models(self):
        expected = [
            FarmerProfile, ManualSoilReport, BuyerProfile, DirectTradeProposal,
            SellerProfile, MarketplaceListing, InputOrder, EscrowTransaction,
            GridSoilData, WeatherHistory, UnifiedReview,
        ]
        for model in expected:
            self.assertTrue(hasattr(model, '_meta'))

    def test_escrow_and_payment_share_transaction_model(self):
        self.assertIs(EscrowTransaction, EscrowTransactionFromEscrow)

    def test_safe_soil_defaults_are_complete(self):
        data = get_safe_defaults()
        for key in ('pH', 'N', 'P', 'K', 'found', 'Status'):
            self.assertIn(key, data)

    def test_geocoder_has_kerala_districts(self):
        geocoder = IndianAgriGeocoder()
        self.assertIn('pathanamthitta', geocoder.kerala_districts)

    def test_crop_prediction_boundary_is_callable(self):
        self.assertTrue(callable(predict_best_crop))

    def test_advisory_boundary_handles_unknown_crop(self):
        self.assertIsNone(get_crop_advisory('__unknown_crop__'))


if __name__ == '__main__':
    unittest.main()
