"""Single nearest-pixel ROI."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from ..geometry.nearest import find_nearest_pixel
from .base import ROI, ROISelection


class PixelROI(ROI):
    """Selects only the single pixel nearest to (longitude, latitude)."""

    def __init__(self, longitude: float, latitude: float):
        self.longitude = float(longitude)
        self.latitude = float(latitude)

    def select(
        self,
        longitude_grid: np.ndarray,
        latitude_grid: np.ndarray,
        max_search_radius_km: Optional[float] = None,
    ) -> ROISelection:
        mask = np.zeros(longitude_grid.shape, dtype=bool)
        nearest = find_nearest_pixel(
            longitude_grid, latitude_grid, self.longitude, self.latitude, max_search_radius_km
        )
        if nearest is None:
            return ROISelection(mask=mask, description="single pixel (no coverage)")
        mask[nearest.row, nearest.col] = True
        return ROISelection(
            mask=mask,
            description=f"single nearest pixel to ({self.longitude:.4f}, {self.latitude:.4f})",
            center_row=nearest.row,
            center_col=nearest.col,
            center_distance_km=nearest.distance_km,
        )

    def bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        return (self.longitude, self.longitude, self.latitude, self.latitude)
