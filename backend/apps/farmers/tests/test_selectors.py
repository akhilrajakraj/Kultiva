from django.test import TestCase

from backend.apps.farmers import selectors


class FarmerSelectorBoundaryTests(TestCase):
    """The selector module must expose reads without leaking HTTP concerns."""

    def test_selector_module_exposes_farmer_read_contract(self):
        self.assertTrue(callable(selectors.get_profile))
        self.assertTrue(callable(selectors.get_primary_address))
        self.assertTrue(callable(selectors.list_proposals))
        self.assertTrue(callable(selectors.get_proposal))
        self.assertTrue(callable(selectors.list_input_products))
        self.assertTrue(callable(selectors.get_input_product))
        self.assertTrue(callable(selectors.has_purchased_input))
        self.assertTrue(callable(selectors.get_order_transaction))
