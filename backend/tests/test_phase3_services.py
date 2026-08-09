import os
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from backend.ai.crop_prediction.service import predict_best_crop
from backend.apps.advisory.services import get_crop_advisory
from backend.apps.soil.services import get_safe_defaults
from backend.apps.weather.services import get_weather


class Phase3ServiceTests(unittest.TestCase):
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
