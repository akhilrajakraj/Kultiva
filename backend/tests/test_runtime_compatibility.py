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
            "accounts_boundary",
            "admin_portal_boundary",
            "advisory_boundary",
            "analytics_boundary",
            "buyers_boundary",
            "escrow_boundary",
            "farmers_boundary",
            "marketplace_boundary",
            "notifications_boundary",
            "orders_boundary",
            "payments_boundary",
            "reviews_boundary",
            "sellers_boundary",
            "soil_boundary",
            "weather_boundary",
        }
        installed = {config.label for config in apps.get_app_configs()}
        self.assertTrue(expected.issubset(installed))

    def test_runtime_uses_professional_urlconf(self):
        self.assertEqual(settings.ROOT_URLCONF, "config.urls")
        resolver = get_resolver()
        self.assertGreater(len(resolver.url_patterns), 50)

    def test_legacy_and_professional_urlpatterns_are_the_same_objects(self):
        from Kultiva.urls import urlpatterns as legacy_patterns
        from config.urls import urlpatterns as professional_patterns
        self.assertIs(professional_patterns, legacy_patterns)

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
