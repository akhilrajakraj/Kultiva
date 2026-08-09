import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.db.migrations.loader import MigrationLoader
from django.db import connection
from django.test import SimpleTestCase

from backend.core.legacy.models import (
    DirectTradeProposal,
    FarmerProfile,
    ManualSoilReport,
    MarketplaceListing,
    UnifiedReview,
    User,
)


class LegacyModelContractTests(SimpleTestCase):
    """Guard the compatibility layer against accidental model drift."""

    def test_user_contains_migrated_fields(self):
        self.assertIn("phone_number", {field.name for field in User._meta.get_fields()})
        self.assertIn("role", {field.name for field in User._meta.get_fields()})

    def test_farmer_profile_contains_kissan_id(self):
        fields = {field.name for field in FarmerProfile._meta.get_fields()}
        self.assertIn("kissan_id", fields)

    def test_manual_soil_report_matches_latest_migration_contract(self):
        fields = {field.name for field in ManualSoilReport._meta.get_fields()}
        self.assertIn("farmer", fields)
        self.assertIn("farm_address", fields)
        self.assertIn("report_file", fields)
        self.assertNotIn("land_area", fields)

    def test_trade_proposal_contains_negotiation_fields(self):
        fields = {field.name for field in DirectTradeProposal._meta.get_fields()}
        for expected in (
            "requested_quantity",
            "proposed_price",
            "total_amount",
            "security_token",
            "qr_code",
        ):
            self.assertIn(expected, fields)

    def test_unified_review_contains_migrated_image_field(self):
        fields = {field.name for field in UnifiedReview._meta.get_fields()}
        self.assertIn("image", fields)

    def test_marketplace_listing_has_current_schema_fields(self):
        fields = {field.name for field in MarketplaceListing._meta.get_fields()}
        for expected in (
            "wing",
            "category",
            "available_stock",
            "min_order_quantity",
            "harvest_date",
            "is_organic",
            "grade",
            "specifications",
        ):
            self.assertIn(expected, fields)

    def test_migration_history_is_consistent(self):
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        graph = loader.graph
        self.assertIn(("Kultiva", "0008_manualsoilreport_farm_address"), graph.nodes)
        self.assertIn(("Kultiva", "0007_unifiedreview_image"), graph.nodes)
        self.assertIn(("Kultiva", "0006_directtradeproposal_total_amount_and_more"), graph.nodes)
        self.assertIn(("Kultiva", "0005_farmerprofile_kissan_id"), graph.nodes)
        self.assertIn(("Kultiva", "0004_alter_manualsoilreport_farmer"), graph.nodes)
