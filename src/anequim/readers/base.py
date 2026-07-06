"""Abstract interface every sensor-specific Level-2 reader implements.

Anequim's sensor independence (design principle 1) rests entirely on this
class: the retrieval engine (:mod:`anequim.core.anequim`), ROI selection,
QC, and statistics are all written against these methods only, never
against a specific file format. Adding a new sensor means writing one
new subclass; nothing else in the package needs to change.
"""

from __future__ import annotations

import abc
from typing import Dict, Optional

import numpy as np


class SensorReader(abc.ABC):
    """Abstract base class for a single-granule Level-2 ocean color reader.

    Instances are meant to be used as context managers::

        with SomeReader(path) as reader:
            lon, lat = reader.get_navigation()
            ...

    Subclasses own the underlying file handle and must release it in
    ``close()``.
    """

    #: Canonical short sensor name, e.g. "PACE-OCI". Set by subclasses.
    sensor_name: str = "UNKNOWN"

    def __init__(self, path: str):
        self.path = path

    def __enter__(self) -> "SensorReader":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # -- lifecycle -----------------------------------------------------
    @abc.abstractmethod
    def open(self) -> None:
        """Open the underlying file. Called automatically by ``__enter__``."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release the underlying file handle."""

    # -- sniffing --------------------------------------------------------
    @classmethod
    @abc.abstractmethod
    def matches(cls, path: str) -> bool:
        """Return True if ``path`` looks like a granule this reader can
        handle (typically by checking global attributes cheaply, without
        reading full data arrays)."""

    # -- geolocation & time ----------------------------------------------
    @abc.abstractmethod
    def get_navigation(self) -> "tuple[np.ndarray, np.ndarray]":
        """Return (longitude, latitude) as 2D arrays, shape (rows, cols)."""

    @abc.abstractmethod
    def get_time_coverage(self) -> "tuple[Optional[str], Optional[str]]":
        """Return (time_coverage_start, time_coverage_end) ISO-8601
        strings from the granule's global attributes, if present."""

    def get_scan_line_times(self) -> Optional[np.ndarray]:
        """Optional: per-scan-line overpass times as ``datetime64[ns]``,
        shape (rows,). Return ``None`` if unavailable; callers should then
        fall back to the granule-level midtime from ``get_time_coverage``.
        """
        return None

    # -- spectral data ------------------------------------------------
    @abc.abstractmethod
    def get_wavelengths(self) -> np.ndarray:
        """Return native center wavelengths (nm), shape (n_bands,)."""

    @abc.abstractmethod
    def get_rrs_cube(self) -> np.ndarray:
        """Return the full Rrs pixel cube, shape (rows, cols, n_bands),
        in the sensor's native units (typically sr^-1), with fill values
        already converted to NaN.
        """

    @abc.abstractmethod
    def get_quality_flags(self) -> np.ndarray:
        """Return the per-pixel quality-flag integer array, shape
        (rows, cols) (e.g. OBPG ``l2_flags``)."""

    def get_flag_name_to_bit(self) -> Optional[Dict[str, int]]:
        """Optional: {flag_name: bit_index} mapping read directly from
        this granule's own flag metadata (preferred over the generic
        default table in :mod:`anequim.core.flags` when available).
        Return ``None`` to fall back to the default OBPG table.
        """
        return None

    def get_atmospheric_products(self) -> Dict[str, np.ndarray]:
        """Optional: dict of ancillary per-pixel products, each shape
        (rows, cols) — e.g. "aot_865", "angstrom", "solar_zenith",
        "sensor_zenith", "relative_azimuth", "wind_speed". Readers that
        do not provide these may return an empty dict.
        """
        return {}

    # -- metadata / provenance -------------------------------------------
    def get_platform_name(self) -> Optional[str]:
        return None

    def get_processing_version(self) -> Optional[str]:
        return None
