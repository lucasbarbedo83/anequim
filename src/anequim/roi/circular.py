"""Circular ROI: all pixels within a given great-circle radius of a point."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from ..geometry.distance import haversine_km
from .base import ROI, ROISelection


class CircularROI(ROI):
    """Selects all pixels within ``radius_km`` (great-circle distance) of
    (longitude, latitude).

    Note this computes distance to every pixel in the granule (same cost
    profile as :func:`anequim.geometry.nearest.find_nearest_pixel`), which
    is appropriate for single-granule, single-query use.
    """

    def __init__(self, longitude: float, latitude: float, radius_km: float):
        if radius_km <= 0:
            raise ValueError("radius_km must be positive")
        self.longitude = float(longitude)
        self.latitude = float(latitude)
        self.radius_km = float(radius_km)

    def select(
        self,
        longitude_grid: np.ndarray,
        latitude_grid: np.ndarray,
        max_search_radius_km: Optional[float] = None,
    ) -> ROISelection:
        distances = haversine_km(longitude_grid, latitude_grid, self.longitude, self.latitude)
        finite = np.isfinite(distances)
        mask = finite & (distances <= self.radius_km)

        if not np.any(mask):
            return ROISelection(
                mask=mask, description=f"circular ROI, radius={self.radius_km:.2f} km (no coverage)"
            )

        distances_masked = np.where(finite, distances, np.inf)
        flat_idx = int(np.argmin(distances_masked))
        row, col = np.unravel_index(flat_idx, distances.shape)
        best_distance = float(distances[row, col])

        if max_search_radius_km is not None and best_distance > max_search_radius_km:
            return ROISelection(
                mask=np.zeros_like(mask),
                description=f"circular ROI, radius={self.radius_km:.2f} km (nearest pixel too far)",
            )

        return ROISelection(
            mask=mask,
            description=(
                f"circular ROI, radius={self.radius_km:.2f} km around "
                f"({self.longitude:.4f}, {self.latitude:.4f})"
            ),
            center_row=int(row),
            center_col=int(col),
            center_distance_km=best_distance,
        )

    def bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        # Rough degree-equivalent padding; good enough as a cheap pre-filter.
        pad_deg = self.radius_km / 111.0
        return (
            self.longitude - pad_deg,
            self.longitude + pad_deg,
            self.latitude - pad_deg,
            self.latitude + pad_deg,
        )
