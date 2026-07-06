"""Nearest-pixel search on curvilinear (2D lon/lat) swath grids.

Ocean color Level-2 granules store longitude/latitude as full 2D arrays
(one value per along-track/cross-track pixel) rather than a regular
lat/lon grid, so nearest-neighbor search cannot rely on simple index
arithmetic. This module provides a brute-force (vectorized) search
that is perfectly adequate for single-point or small-ROI queries against
one granule at a time, plus an optional cKDTree-accelerated path for
repeated queries against the same granule.
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Tuple

import numpy as np

from .distance import haversine_km


@dataclasses.dataclass
class NearestPixel:
    """Result of a nearest-pixel search."""

    row: int
    col: int
    distance_km: float
    longitude: float
    latitude: float


def find_nearest_pixel(
    longitude_grid: np.ndarray,
    latitude_grid: np.ndarray,
    target_lon: float,
    target_lat: float,
    max_search_radius_km: Optional[float] = None,
) -> Optional[NearestPixel]:
    """Brute-force nearest-pixel search over a 2D lon/lat grid.

    Parameters
    ----------
    longitude_grid, latitude_grid:
        2D arrays, shape (rows, cols), in decimal degrees.
    target_lon, target_lat:
        Target point, decimal degrees.
    max_search_radius_km:
        If given, return ``None`` instead of a result when the closest
        pixel found is farther than this from the target (guards against
        matching a swath that doesn't actually cover the point).

    Notes
    -----
    This computes the true great-circle distance to every pixel, which is
    O(rows*cols). For a single Level-2 granule (typically <= a few
    million pixels) this comfortably runs in well under a second; it is
    not intended for scanning many granules per call (pre-filter by
    granule bounding box / time first — see
    :func:`anequim.geometry.distance.bounding_box_contains` and
    :mod:`anequim.core.time_utils`).
    """
    lon = np.asarray(longitude_grid, dtype=float)
    lat = np.asarray(latitude_grid, dtype=float)
    if lon.shape != lat.shape:
        raise ValueError("longitude_grid and latitude_grid must have the same shape")

    distances = haversine_km(lon, lat, target_lon, target_lat)
    finite = np.isfinite(distances)
    if not np.any(finite):
        return None
    distances_masked = np.where(finite, distances, np.inf)
    flat_idx = int(np.argmin(distances_masked))
    row, col = np.unravel_index(flat_idx, distances.shape)
    best_distance = float(distances[row, col])

    if max_search_radius_km is not None and best_distance > max_search_radius_km:
        return None

    return NearestPixel(
        row=int(row),
        col=int(col),
        distance_km=best_distance,
        longitude=float(lon[row, col]),
        latitude=float(lat[row, col]),
    )


def box_slice(
    row: int, col: int, box_radius: int, shape: Tuple[int, int]
) -> Tuple[slice, slice]:
    """Row/column slices for a square box of radius ``box_radius`` pixels
    centered on (row, col), clipped to the array ``shape`` bounds.
    A box_radius of 2 gives a 5x5 box (2 pixels on each side of center).
    """
    n_rows, n_cols = shape
    r0 = max(row - box_radius, 0)
    r1 = min(row + box_radius + 1, n_rows)
    c0 = max(col - box_radius, 0)
    c1 = min(col + box_radius + 1, n_cols)
    return slice(r0, r1), slice(c0, c1)


class KDTreePixelFinder:
    """cKDTree-accelerated nearest-pixel finder for repeated queries
    against the same granule grid (e.g. many target points against one
    file). Falls back gracefully if scipy is not installed by raising
    ImportError only when actually instantiated.
    """

    def __init__(self, longitude_grid: np.ndarray, latitude_grid: np.ndarray):
        try:
            from scipy.spatial import cKDTree
        except ImportError as exc:  # pragma: no cover - exercised only without scipy
            raise ImportError(
                "scipy is required for KDTreePixelFinder; use find_nearest_pixel() "
                "for a dependency-free (if slower for many repeated queries) alternative"
            ) from exc

        self._lon = np.asarray(longitude_grid, dtype=float)
        self._lat = np.asarray(latitude_grid, dtype=float)
        self._shape = self._lon.shape

        # Convert to unit-sphere Cartesian coordinates for a Euclidean
        # KD-tree that still respects great-circle proximity reasonably
        # well at the pixel scale relevant here.
        lon_rad = np.radians(self._lon.ravel())
        lat_rad = np.radians(self._lat.ravel())
        x = np.cos(lat_rad) * np.cos(lon_rad)
        y = np.cos(lat_rad) * np.sin(lon_rad)
        z = np.sin(lat_rad)
        points = np.column_stack([x, y, z])
        self._tree = cKDTree(points)

    def query(
        self, target_lon: float, target_lat: float, max_search_radius_km: Optional[float] = None
    ) -> Optional[NearestPixel]:
        lon_rad = np.radians(target_lon)
        lat_rad = np.radians(target_lat)
        qx = np.cos(lat_rad) * np.cos(lon_rad)
        qy = np.cos(lat_rad) * np.sin(lon_rad)
        qz = np.sin(lat_rad)
        _, flat_idx = self._tree.query([qx, qy, qz])
        row, col = np.unravel_index(int(flat_idx), self._shape)
        distance_km = float(
            haversine_km(self._lon[row, col], self._lat[row, col], target_lon, target_lat)
        )
        if max_search_radius_km is not None and distance_km > max_search_radius_km:
            return None
        return NearestPixel(
            row=int(row),
            col=int(col),
            distance_km=distance_km,
            longitude=float(self._lon[row, col]),
            latitude=float(self._lat[row, col]),
        )
