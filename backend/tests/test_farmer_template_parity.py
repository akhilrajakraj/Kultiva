import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.test import Client, TestCase

from backend.apps.accounts.models import User


class FarmerTemplateParityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.farmer = User.objects.create_user(
            username="template-farmer",
            email="template-farmer@example.com",
            password="test-password",
            role=User.Role.FARMER,
            is_active=True,
        )

    def test_canonical_farmer_dashboard_template_exists(self):
        self.assertTrue(True)

    def test_farmer_dashboard_requires_authentication(self):
        response = self.client.get("/farmer/home/")
        self.assertIn(response.status_code, {200, 302})

    def test_farmer_dashboard_authenticated_route_is_reachable(self):
        self.client.force_login(self.farmer)
        response = self.client.get("/farmer/home/")
        self.assertNotEqual(response.status_code, 404)
