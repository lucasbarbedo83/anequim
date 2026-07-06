"""Rectangular (square box) ROI centered on the nearest pixel — the
default ROI used for Bailey & Werdell (2006)-style Rrs match-ups.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from ..geometry.nearest import find_nearest_pixel, box_slice
from .base import ROI, ROISelection


class RectangularROI(ROI):
    """Selects an ``n_rows x n_cols`` pixel box centered on the pixel
    nearest to (longitude, latitude).

    Parameters
    ----------
    longitude, latitude:
        Reference point, decimal degrees.
    box_size:
        Side length in pixels for a square box (mutually exclusive with
        ``n_rows``/``n_cols``). Must be odd.
    n_rows, n_cols:
        Explicit (possibly non-square) box dimensions in pixels, each
        must be odd, if ``box_size`` is not given.
    """

    def __init__(
        self,
        longitude: float,
        latitude: float,
        box_size: Optional[int] = 5,
        n_rows: Optional[int] = None,
        n_cols: Optional[int] = None,
    ):
        self.longitude = float(longitude)
        self.latitude = float(latitude)
        if n_rows is None and n_cols is None:
            if box_size is None or box_size < 1 or box_size % 2 == 0:
                raise ValueError("box_size must be a positive odd integer")
            n_rows = n_cols = box_size
        if n_rows is None or n_cols is None:
            raise ValueError("must provide both n_rows and n_cols together, or box_size")
        if n_rows < 1 or n_rows % 2 == 0 or n_cols < 1 or n_cols % 2 == 0:
            raise ValueError("n_rows and n_cols must be positive odd integers")
        self.n_rows = n_rows
        self.n_cols = n_cols

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
            return ROISelection(
                mask=mask, description=f"{self.n_rows}x{self.n_cols} box (no coverage)"
            )

        row_radius = self.n_rows // 2
        col_radius = self.n_cols // 2
        r0 = max(nearest.row - row_radius, 0)
        r1 = min(nearest.row + row_radius + 1, longitude_grid.shape[0])
        c0 = max(nearest.col - col_radius, 0)
        c1 = min(nearest.col + col_radius + 1, longitude_grid.shape[1])
        mask[r0:r1, c0:c1] = True

        return ROISelection(
            mask=mask,
            description=(
                f"{self.n_rows}x{self.n_cols} pixel box centered on nearest pixel to "
                f"({self.longitude:.4f}, {self.latitude:.4f})"
            ),
            center_row=nearest.row,
            center_col=nearest.col,
            center_distance_km=nearest.distance_km,
        )

    def bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        return (self.longitude, self.longitude, self.latitude, self.latitude)
