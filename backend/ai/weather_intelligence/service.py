"""Weather intelligence boundary for the existing 3-tier weather engine."""
from backend.core.legacy.services import get_weather, IndianAgriGeocoder

__all__ = ['get_weather', 'IndianAgriGeocoder']
