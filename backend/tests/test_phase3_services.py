import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.test import TestCase

from backend.ai.crop_prediction.service import predict_best_crop
from backend.apps.accounts.models import User
from backend.apps.advisory.services import get_crop_advisory
from backend.apps.farmers.models import FarmerProfile, ManualSoilReport
from backend.apps.farmers.services import FarmerService
from backend.apps.soil.services import get_safe_defaults
from backend.apps.weather.services import get_weather


class Phase3ServiceTests(TestCase):
    def test_soil_service_returns_complete_safe_contract(self):
        data = get_safe_defaults()
        for key in ("pH", "N", "P", "K", "found", "Status"):
            self.assertIn(key, data)

    def test_advisory_service_handles_unknown_crop(self):
        self.assertIsNone(get_crop_advisory("__unknown_crop__"))

    def test_weather_service_returns_contract(self):
        data = get_weather(9.2648, 76.7870, "Pathanamthitta")
        for key in ("Temperature_C", "Humidity_Pct", "Rainfall_mm", "Source", "Status"):
            self.assertIn(key, data)

    def test_crop_prediction_service_is_callable(self):
        self.assertTrue(callable(predict_best_crop))

    def _create_farmer(self, username="farmer-service-test"):
        return User.objects.create_user(
            username=username,
            password="test-password",
            role=User.Role.FARMER,
        )

    def test_farmer_service_creates_profile(self):
        user = self._create_farmer()

        profile = FarmerService.create_profile(
            user=user,
            aadhar_no="123456789012",
            land_area=2.5,
            soil_type="Loamy",
            irrigation="Drip",
        )

        self.assertIsInstance(profile, FarmerProfile)
        self.assertEqual(profile.user_id, user.user_id)
        self.assertEqual(profile.land_area, 2.5)

    def test_farmer_service_rejects_non_farmer_profile_creation(self):
        user = User.objects.create_user(
            username="buyer-service-test",
            password="test-password",
            role=User.Role.BUYER,
        )

        with self.assertRaises(ValueError):
            FarmerService.create_profile(
                user=user,
                aadhar_no="123456789013",
                land_area=1.0,
                soil_type="Loamy",
                irrigation="Rain",
            )

    def test_farmer_service_updates_only_allowed_profile_fields(self):
        user = self._create_farmer()
        FarmerService.create_profile(
            user=user,
            aadhar_no="123456789014",
            land_area=2.0,
            soil_type="Loamy",
            irrigation="Rain",
        )

        profile = FarmerService.update_profile(
            user=user,
            changes={"land_area": 4.0, "irrigation": "Drip"},
        )

        self.assertEqual(profile.land_area, 4.0)
        self.assertEqual(profile.irrigation, "Drip")

        with self.assertRaises(ValueError):
            FarmerService.update_profile(user=user, changes={"user": user})

    def test_farmer_service_creates_and_completes_manual_soil_report(self):
        user = self._create_farmer()

        report = FarmerService.request_manual_soil_report(
            user=user,
            land_area=3.0,
            previous_crop="Rice",
        )
        self.assertIsInstance(report, ManualSoilReport)
        self.assertEqual(report.request_status, "PENDING")
        self.assertEqual(report.land_area, 3.0)

        completed = FarmerService.complete_manual_soil_report(
            user=user,
            nitrogen=80.0,
            phosphorus=40.0,
            potassium=60.0,
            ph=6.5,
        )

        self.assertEqual(completed.request_status, "COMPLETED")
        self.assertEqual(completed.n, 80.0)
        self.assertEqual(completed.p, 40.0)
        self.assertEqual(completed.k, 60.0)
        self.assertEqual(completed.ph, 6.5)

    def test_completed_manual_report_cannot_be_reopened(self):
        user = self._create_farmer()
        FarmerService.request_manual_soil_report(user=user)
        FarmerService.complete_manual_soil_report(
            user=user,
            nitrogen=80.0,
            phosphorus=40.0,
            potassium=60.0,
            ph=6.5,
        )

        with self.assertRaises(ValueError):
            FarmerService.request_manual_soil_report(user=user, land_area=5.0)
