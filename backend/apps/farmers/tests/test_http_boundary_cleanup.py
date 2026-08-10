from django.test import SimpleTestCase

from backend.apps.farmers import selectors, services


class FarmerHttpBoundaryCleanupTests(SimpleTestCase):
    def test_address_update_is_owned_by_service(self):
        self.assertTrue(hasattr(services.FarmerService, "update_address"))

    def test_latest_soil_report_query_is_owned_by_selector(self):
        self.assertTrue(hasattr(selectors, "get_latest_soil_report"))

    def test_address_ownership_query_is_owned_by_selector(self):
        self.assertTrue(hasattr(selectors, "is_farmer_address"))

    def test_produce_listing_lookup_is_owned_by_selector(self):
        self.assertTrue(hasattr(selectors, "get_produce_listing"))
