"""Compatibility service exports from the legacy runtime."""
from Kultiva.utils import (
    get_weather,
    get_soil_for_location,
    get_safe_defaults,
    predict_best_crop,
    IndianAgriGeocoder,
)

__all__ = [
    'get_weather', 'get_soil_for_location', 'get_safe_defaults',
    'predict_best_crop', 'IndianAgriGeocoder',
]
