"""Estimate actual ground pixel size and ROI footprint directly from a
granule's own 2D lon/lat geolocation grid.

Nominal, sensor-specification pixel sizes (e.g. "OLCI is 300 m", "PACE
OCI is ~1 km") only describe the nadir case — real pixels grow
substantially off-nadir (more so for wide-swath sensors like VIIRS/OLCI
due to the bow-tie effect), and swath geometry means neighboring pixels
are not perfectly axis-aligned either. Measuring directly from the
navigation grid at the actual matched location is more accurate and
sensor-independent, so it is what anequim reports in
:class:`~anequim.core.provenance.Provenance` — the nominal value is
kept only as reference metadata (``SensorReader.nominal_pixel_size_m``).
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import numpy as np

from .distance import haversine_km


@dataclasses.dataclass
class PixelSize:
    """Estimated ground pixel size at a specific location in a granule.

    Attributes
    ----------
    along_track_km, cross_track_km:
        Distance (km) to the neighboring pixel in the along-track (row)
        and cross-track (column) directions, respectively — i.e. the
        two edge lengths of the local pixel "cell".
    mean_km:
        Geometric mean of the two, a single representative pixel size.
    area_km2:
        Approximate pixel area (along_track_km * cross_track_km),
        treating the local cell as a parallelogram/rectangle — accurate
        enough at pixel scale even though real pixel footprints are not
        perfect rectangles.
    """

    along_track_km: float
    cross_track_km: float
    mean_km: float
    area_km2: float


def estimate_pixel_size_km(
    longitude_grid: np.ndarray, latitude_grid: np.ndarray, row: int, col: int
) -> Optional[PixelSize]:
    """Estimate the ground pixel size at grid position (row, col) by
    measuring the distance to its immediate row/column neighbors.

    Falls back to the previous neighbor (row-1 / col-1) at the far edge
    of the grid where a "next" neighbor doesn't exist. Returns ``None``
    if the grid is too small (fewer than 2 rows or columns) to measure
    any neighbor distance at all.
    """
    n_rows, n_cols = longitude_grid.shape
    if n_rows < 2 or n_cols < 2:
        return None

    row_other = row + 1 if row + 1 < n_rows else row - 1
    col_other = col + 1 if col + 1 < n_cols else col - 1

    along_track_km = float(
        haversine_km(
            longitude_grid[row, col], latitude_grid[row, col],
            longitude_grid[row_other, col], latitude_grid[row_other, col],
        )
    )
    cross_track_km = float(
        haversine_km(
            longitude_grid[row, col], latitude_grid[row, col],
            longitude_grid[row, col_other], latitude_grid[row, col_other],
        )
    )

    if not (np.isfinite(along_track_km) and np.isfinite(cross_track_km)):
        return None

    mean_km = float(np.sqrt(along_track_km * cross_track_km)) if along_track_km * cross_track_km > 0 else 0.0
    area_km2 = along_track_km * cross_track_km

    return PixelSize(
        along_track_km=along_track_km,
        cross_track_km=cross_track_km,
        mean_km=mean_km,
        area_km2=area_km2,
    )


def estimate_roi_footprint_km(
    longitude_grid: np.ndarray, latitude_grid: np.ndarray, mask: np.ndarray
) -> Optional[dict]:
    """Estimate the overall footprint of a selected ROI mask.

    Uses the bounding box (in row/column index space) of the True
    entries in ``mask``, then measures the along-track and cross-track
    extent of that bounding box in kilometers via great-circle distance
    between its corner pixels. This is exact for a rectangular ROI
    (the common case — :class:`anequim.roi.rectangular.RectangularROI`,
    :class:`anequim.roi.pixel.PixelROI`) and a reasonable approximation
    (the bounding box of the true footprint) for non-rectangular ROIs
    (circular, bounding-box-by-lonlat).

    Returns ``None`` if ``mask`` has no True entries.
    """
    rows_with_selection = np.where(mask.any(axis=1))[0]
    cols_with_selection = np.where(mask.any(axis=0))[0]
    if rows_with_selection.size == 0 or cols_with_selection.size == 0:
        return None

    r0, r1 = int(rows_with_selection.min()), int(rows_with_selection.max())
    c0, c1 = int(cols_with_selection.min()), int(cols_with_selection.max())
    n_rows = r1 - r0 + 1
    n_cols = c1 - c0 + 1

    # Along-track extent: distance from the top edge to the bottom edge,
    # both taken at the same (middle) column for a fair comparison.
    mid_col = (c0 + c1) // 2
    along_track_km = float(
        haversine_km(
            longitude_grid[r0, mid_col], latitude_grid[r0, mid_col],
            longitude_grid[r1, mid_col], latitude_grid[r1, mid_col],
        )
    )
    mid_row = (r0 + r1) // 2
    cross_track_km = float(
        haversine_km(
            longitude_grid[mid_row, c0], latitude_grid[mid_row, c0],
            longitude_grid[mid_row, c1], latitude_grid[mid_row, c1],
        )
    )
    diagonal_km = float(
        haversine_km(
            longitude_grid[r0, c0], latitude_grid[r0, c0],
            longitude_grid[r1, c1], latitude_grid[r1, c1],
        )
    )

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "along_track_km": along_track_km,
        "cross_track_km": cross_track_km,
        "diagonal_km": diagonal_km,
    }
