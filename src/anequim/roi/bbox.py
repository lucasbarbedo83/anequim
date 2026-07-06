"""Bounding-box ROI: all pixels within a lon/lat rectangle."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .base import ROI, ROISelection


class BoundingBoxROI(ROI):
    """Selects all pixels within an explicit longitude/latitude bounding
    box. Handles antimeridian-crossing boxes (``lon_min > lon_max``) by
    wrapping longitudes into a continuous range before comparison.
    """

    def __init__(self, lon_min: float, lon_max: float, lat_min: float, lat_max: float):
        if lat_min > lat_max:
            raise ValueError("lat_min must be <= lat_max")
        self.lon_min = float(lon_min)
        self.lon_max = float(lon_max)
        self.lat_min = float(lat_min)
        self.lat_max = float(lat_max)

    def select(
        self,
        longitude_grid: np.ndarray,
        latitude_grid: np.ndarray,
        max_search_radius_km: Optional[float] = None,
    ) -> ROISelection:
        lon = np.asarray(longitude_grid, dtype=float)
        lat = np.asarray(latitude_grid, dtype=float)

        lat_ok = (lat >= self.lat_min) & (lat <= self.lat_max)
        if self.lon_max >= self.lon_min:
            lon_ok = (lon >= self.lon_min) & (lon <= self.lon_max)
        else:
            wrapped = np.where(lon >= self.lon_min, lon, lon + 360.0)
            lon_ok = (wrapped >= self.lon_min) & (wrapped <= self.lon_max + 360.0)

        mask = lat_ok & lon_ok & np.isfinite(lon) & np.isfinite(lat)
        description = (
            f"bounding box lon=[{self.lon_min:.4f}, {self.lon_max:.4f}], "
            f"lat=[{self.lat_min:.4f}, {self.lat_max:.4f}]"
        )
        if not np.any(mask):
            return ROISelection(mask=mask, description=description + " (no coverage)")
        return ROISelection(mask=mask, description=description)

    def bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        return (self.lon_min, self.lon_max, self.lat_min, self.lat_max)
