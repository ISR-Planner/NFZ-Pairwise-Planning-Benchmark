"""Lat/lng <-> local-km projection helpers and geodesic distance.

All distances are kilometers. Projections are equirectangular around a
caller-supplied reference lat/lng — accurate for mission-scale areas
(<100 km across). For longer distances use haversine_km directly.
"""

import math

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 111.32  # constant (to ~0.1%)


def km_per_deg_lng(ref_lat: float) -> float:
    return KM_PER_DEG_LAT * math.cos(math.radians(ref_lat))


def latlng_to_local_xy(
    lat: float, lng: float, ref_lat: float, ref_lng: float
) -> tuple[float, float]:
    """Project (lat, lng) to local (x_km east, y_km north) around (ref_lat, ref_lng)."""
    x_km = (lng - ref_lng) * km_per_deg_lng(ref_lat)
    y_km = (lat - ref_lat) * KM_PER_DEG_LAT
    return x_km, y_km


def local_xy_to_latlng(
    x_km: float, y_km: float, ref_lat: float, ref_lng: float
) -> tuple[float, float]:
    """Inverse of latlng_to_local_xy."""
    lat = ref_lat + y_km / KM_PER_DEG_LAT
    lng = ref_lng + x_km / km_per_deg_lng(ref_lat)
    return lat, lng


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometers."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
