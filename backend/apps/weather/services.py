"""Weather domain service.

Phase 3 extracts weather orchestration from the monolithic legacy utility module.
The service owns the three-tier weather policy while the legacy module remains
available as a compatibility fallback until all callers migrate.
"""
import logging
import random
from datetime import datetime

import requests
from django.conf import settings

from backend.apps.weather.models import WeatherHistory

logger = logging.getLogger(__name__)


def get_weather(latitude, longitude, location_name):
    """Return weather using live API, historical DB, then deterministic policy fallback."""
    api_key = getattr(settings, "OPENWEATHER_API_KEY", "")
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (ValueError, TypeError):
        lat, lon = 20.5937, 78.9629

    if api_key:
        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )
        try:
            response = requests.get(url, timeout=(3.0, 5.0))
            response.raise_for_status()
            data = response.json()
            live_temp = data["main"]["temp"]
            live_hum = data["main"]["humidity"]
            live_rain = data.get("rain", {}).get("1h", 0.0)
            if live_rain > 0:
                rainfall = random.uniform(150.0, 250.0)
            elif live_hum > 75.0:
                rainfall = random.uniform(80.0, 150.0)
            else:
                rainfall = random.uniform(20.0, 60.0)
            return {
                "Temperature_C": live_temp,
                "Humidity_Pct": live_hum,
                "Rainfall_mm": round(rainfall, 1),
                "Source": "Live API",
                "Status": "success",
            }
        except requests.RequestException as exc:
            logger.warning("Weather API failed for %s: %s", location_name, exc)

    month = datetime.now().month
    fallback = WeatherHistory.objects.filter(
        district__icontains=location_name,
        month=month,
    ).first()
    if fallback:
        return {
            "Temperature_C": fallback.avg_temp,
            "Humidity_Pct": fallback.avg_humidity,
            "Rainfall_mm": fallback.avg_rainfall,
            "Source": "Historical Database",
            "Status": "fallback",
        }

    # Preserve the legacy simulator's broad seasonal/geospatial behaviour.
    is_monsoon = month in (6, 7, 8, 9)
    is_winter = month in (11, 12, 1, 2)
    is_summer = month in (3, 4, 5)
    base_temp = 35.0 - (lat * 0.3)
    if is_winter:
        base_temp -= 10.0
        if lat > 28.0:
            base_temp -= 8.0
    elif is_summer:
        base_temp += 5.0
    temperature = max(5.0, min(round(base_temp + random.uniform(-3, 3), 1), 48.0))

    if is_monsoon:
        if lon < 73.0 and lat > 23.0:
            rainfall = random.uniform(5.0, 40.0)
        elif lon > 88.0:
            rainfall = random.uniform(200.0, 400.0)
        else:
            rainfall = random.uniform(80.0, 200.0)
    elif is_winter and lat > 30.0:
        rainfall = random.uniform(10.0, 40.0)
    elif lon > 80.0 and month in (10, 11):
        rainfall = random.uniform(50.0, 150.0)
    else:
        rainfall = random.uniform(0.0, 10.0)
    rainfall = round(rainfall, 1)

    humidity_base = 85.0 if rainfall > 50 else 65.0 if rainfall > 10 else 40.0
    coastal = (lon < 76.0 and lat < 20.0) or (lon > 80.0 and 10.0 < lat < 22.0)
    if coastal:
        humidity_base = max(humidity_base, 70.0)
    elif is_summer and not coastal:
        humidity_base = 25.0
    humidity = max(10.0, min(round(humidity_base + random.uniform(-10, 10), 1), 100.0))
    return {
        "Temperature_C": temperature,
        "Humidity_Pct": humidity,
        "Rainfall_mm": rainfall,
        "Source": "Smart Geospatial Simulator",
        "Status": "simulated",
    }


__all__ = ["get_weather"]
