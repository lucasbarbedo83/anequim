"""Region-of-interest (ROI) abstraction.

Every ROI type implements :meth:`ROI.select`, which takes a granule's 2D
longitude/latitude grids and returns an :class:`ROISelection` — a boolean
mask over that grid plus descriptive metadata. The match-up engine
(:mod:`anequim.core.anequim`) is written against this interface only, so
new ROI shapes (e.g. a future polygon ROI) do not require touching
reader or QC code.
"""

from __future__ import annotations

import abc
import dataclasses
from typing import Optional, Tuple

import numpy as np


@dataclasses.dataclass
class ROISelection:
    """Result of applying an ROI to a granule's geolocation grid.

    Attributes
    ----------
    mask:
        Boolean array, same shape as the granule's lon/lat grids, True
        for pixels included in the ROI.
    description:
        Human-readable description, used in provenance records.
    center_row, center_col:
        Index of the nearest pixel to the ROI's reference point, if
        applicable (used as the anchor for box slicing / provenance).
    center_distance_km:
        Distance from the reference point to the nearest pixel, if
        applicable.
    """

    mask: np.ndarray
    description: str
    center_row: Optional[int] = None
    center_col: Optional[int] = None
    center_distance_km: Optional[float] = None

    @property
    def n_selected(self) -> int:
        return int(np.count_nonzero(self.mask))


class ROI(abc.ABC):
    """Abstract base class for all region-of-interest selectors."""

    @abc.abstractmethod
    def select(
        self,
        longitude_grid: np.ndarray,
        latitude_grid: np.ndarray,
        max_search_radius_km: Optional[float] = None,
    ) -> ROISelection:
        """Return an :class:`ROISelection` for this ROI applied to the
        given granule geolocation grids. Implementations should return a
        selection with an all-False mask (rather than raising) when the
        ROI does not intersect the granule at all, so callers can treat
        "no coverage" uniformly across ROI types.
        """
        raise NotImplementedError

    def bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        """Optional (lon_min, lon_max, lat_min, lat_max) hint usable for
        cheap granule pre-filtering before opening a file. Returning
        ``None`` means "no cheap hint available; always check properly".
        """
        return None
