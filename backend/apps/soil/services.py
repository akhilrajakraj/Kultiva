"""Soil domain service extracted from the legacy utility layer."""
from backend.apps.soil.models import GridSoilData


def get_safe_defaults():
    return {
        "found": False,
        "lat_used": 0.0,
        "lon_used": 0.0,
        "pH": 6.5,
        "EC": 0.5,
        "OC": 0.5,
        "N": 280.0,
        "P": 25.0,
        "K": 150.0,
        "S": 15.0,
        "Zn": 1.0,
        "Fe": 10.0,
        "Cu": 1.0,
        "Mn": 5.0,
        "B": 0.5,
        "Advisory": "Location outside mapped grid. Showing Standard Regional Recommendations.",
        "Status": "Regional Fallback Used",
    }


def get_soil_for_location(exact_lat, exact_lon):
    """Snap GPS coordinates to the 0.05 grid and return SHC data or safe defaults."""
    try:
        grid_lat = round(float(exact_lat) * 20) / 20
        grid_lon = round(float(exact_lon) * 20) / 20
        soil = GridSoilData.objects.filter(grid_lat=grid_lat, grid_lon=grid_lon).first()
        if not soil:
            return get_safe_defaults()
        return {
            "found": True,
            "lat_used": grid_lat,
            "lon_used": grid_lon,
            "pH": soil.ph,
            "EC": soil.ec,
            "OC": soil.oc,
            "N": soil.avg_n,
            "P": soil.avg_p,
            "K": soil.avg_k,
            "S": soil.avg_s,
            "Zn": soil.avg_zn,
            "Fe": soil.avg_fe,
            "Cu": soil.avg_cu,
            "Mn": soil.avg_mn,
            "B": soil.avg_b,
            "Advisory": soil.recommendation_text,
            "Status": "SHC Data Retrieved Successfully",
        }
    except (TypeError, ValueError):
        return get_safe_defaults()


__all__ = ["get_safe_defaults", "get_soil_for_location"]
