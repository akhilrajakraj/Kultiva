import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.urls import get_resolver


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_professional_domain_apps_are_installed(self):
        expected = {
            "accounts_boundary", "admin_portal_boundary", "advisory_boundary",
            "analytics_boundary", "buyers_boundary", "escrow_boundary",
            "farmers_boundary", "marketplace_boundary", "notifications_boundary",
            "orders_boundary", "payments_boundary", "reviews_boundary",
            "sellers_boundary", "soil_boundary", "weather_boundary",
        }
        installed = {config.label for config in apps.get_app_configs()}
        self.assertTrue(expected.issubset(installed))

    def test_runtime_uses_professional_urlconf(self):
        self.assertEqual(settings.ROOT_URLCONF, "config.urls")
        resolver = get_resolver()
        self.assertGreater(len(resolver.url_patterns), 50)

    def test_extracted_routes_replace_legacy_routes_without_duplicates(self):
        from Kultiva.urls import urlpatterns as legacy_patterns
        from config.urls import urlpatterns as professional_patterns

        legacy_names = {
            getattr(pattern, "name", None)
            for pattern in legacy_patterns
            if getattr(pattern, "name", None)
        }
        professional_names = {
            getattr(pattern, "name", None)
            for pattern in professional_patterns
            if getattr(pattern, "name", None)
        }

        extracted_names = {
            "farmer_profile", "add_farmer_listing", "farmer_manage_crops",
            "farmer_proposals", "farmer_input_market", "farmer_orders",
            "seller_dashboard", "add_seller_listing", "manage_stock",
            "remove_listing", "edit_listing", "seller_profile", "seller_orders",
            "seller_reports", "export_seller_orders_csv", "seller_receipt_detail",
            "update_order_status", "seller_order_detail",
        }

        self.assertTrue(extracted_names.issubset(professional_names))
        self.assertTrue(extracted_names.intersection(legacy_names))

        # Professional URL configuration must contain only one route for each
        # extracted name, preventing the legacy route from shadowing the domain view.
        for name in extracted_names:
            matches = [pattern for pattern in professional_patterns if getattr(pattern, "name", None) == name]
            self.assertEqual(len(matches), 1, name)

    def test_legacy_migration_authority_is_preserved(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "Kultiva.User")
        self.assertTrue(any(config.label == "Kultiva" for config in apps.get_app_configs()))
        self.assertEqual(apps.get_app_config("Kultiva").name, "Kultiva")

    def test_domain_apps_have_no_local_migrations(self):
        for label in (
            "accounts_boundary", "buyers_boundary", "farmers_boundary",
            "sellers_boundary", "marketplace_boundary", "orders_boundary",
            "payments_boundary", "escrow_boundary", "reviews_boundary",
            "soil_boundary", "weather_boundary",
        ):
            config = apps.get_app_config(label)
            self.assertFalse(config.path.endswith("/migrations"))


if __name__ == "__main__":
    unittest.main()
