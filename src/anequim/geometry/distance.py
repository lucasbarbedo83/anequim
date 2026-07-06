"""Great-circle distance and related geometric helpers."""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    lon1: np.ndarray, lat1: np.ndarray, lon2: np.ndarray, lat2: np.ndarray
) -> np.ndarray:
    """Great-circle distance in kilometers between (lon1, lat1) and
    (lon2, lat2), vectorized over numpy arrays (broadcastable shapes).
    All inputs in decimal degrees.
    """
    lon1 = np.radians(np.asarray(lon1, dtype=float))
    lat1 = np.radians(np.asarray(lat1, dtype=float))
    lon2 = np.radians(np.asarray(lon2, dtype=float))
    lat2 = np.radians(np.asarray(lat2, dtype=float))

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return EARTH_RADIUS_KM * c


def bounding_box_contains(
    lon: float, lat: float, lon_min: float, lon_max: float, lat_min: float, lat_max: float
) -> bool:
    """Simple lon/lat bounding-box containment test. Does not attempt to
    handle antimeridian-crossing boxes specially beyond wrapping lon into
    [lon_min, lon_min + 360) before comparison when lon_max < lon_min.
    """
    if lat < lat_min or lat > lat_max:
        return False
    if lon_max >= lon_min:
        return lon_min <= lon <= lon_max
    # Antimeridian-crossing box (e.g. lon_min=170, lon_max=-170)
    wrapped = lon if lon >= lon_min else lon + 360.0
    return lon_min <= wrapped <= (lon_max + 360.0)


def approx_pixel_size_km(latitude: float, along_track_km: float, cross_track_km: float) -> float:
    """Rough characteristic pixel footprint size at a given latitude,
    used only for sanity-check radii, not for precise calculations.
    Returns the geometric mean of along- and cross-track resolutions.
    """
    return float(np.sqrt(along_track_km * cross_track_km))
