"""Polygon ROI — planned, not yet implemented.

Design (for a future release): accept a sequence of (lon, lat) vertices
or a ``shapely.geometry.Polygon``, and implement point-in-polygon testing
vectorized over a granule's 2D lon/lat grid (e.g. via a matplotlib.path
or shapely.vectorized point-in-polygon test), with the same
:class:`~anequim.roi.base.ROISelection` return contract as the other ROI
types so it drops into the retrieval engine unchanged.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np

from ..core.exceptions import ROIError
from .base import ROI, ROISelection


class PolygonROI(ROI):
    """Not yet implemented. Present so the ROI API surface is stable and
    user code can be written against it ahead of the real implementation.
    """

    def __init__(self, vertices: Sequence[Tuple[float, float]]):
        if len(vertices) < 3:
            raise ROIError("A polygon ROI needs at least 3 (lon, lat) vertices")
        self.vertices = list(vertices)

    def select(
        self,
        longitude_grid: np.ndarray,
        latitude_grid: np.ndarray,
        max_search_radius_km: Optional[float] = None,
    ) -> ROISelection:
        raise NotImplementedError(
            "PolygonROI is planned but not yet implemented. Use RectangularROI, "
            "CircularROI, or BoundingBoxROI for now."
        )
