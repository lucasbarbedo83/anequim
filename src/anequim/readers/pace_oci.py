"""Reader for PACE / OCI Level-2 ``OC_AOP`` (apparent optical properties)
granules.

File layout assumed (matches NASA OB.DAAC PACE OCI L2 OC_AOP products):

- Global attributes: ``platform``, ``instrument``, ``processing_version``,
  ``time_coverage_start``, ``time_coverage_end``.
- Group ``navigation_data``: ``longitude``, ``latitude`` — 2D,
  shape (number_of_lines, pixels_per_line).
- Group ``sensor_band_parameters``: ``wavelength_3d`` — 1D hyperspectral
  band centers (nm) for the ``Rrs`` product (OCI's blue/red hyperspectral
  bands, roughly 339-719 nm, plus a handful of SWIR bands on some
  products).
- Group ``geophysical_data``: ``Rrs`` — 3D,
  shape (number_of_lines, pixels_per_line, wavelength_3d); ``l2_flags``
  — 2D per-pixel quality flags; plus assorted ancillary products such as
  ``aot_865``, ``angstrom``, ``avw``, when present.
- Group ``scan_line_attributes``: ``year``, ``day``, ``msec`` — per
  scan-line time components (classic OBPG encoding).

Ancillary geometry/meteorology products (solar/sensor zenith, relative
azimuth, wind speed) are looked up defensively across several
plausible group/name combinations and are simply omitted if not found,
since exact placement can vary across processing versions — always check
``SpectralCube.atmospheric.keys()`` for what was actually available in a
given file rather than assuming a fixed set.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from ..core import time_utils
from ..core.exceptions import GranuleFormatError
from .base import SensorReader

# Candidate (group, variable) locations to probe for ancillary products.
# The first match found in each product's candidate list wins.
_ATMOSPHERIC_CANDIDATES: Dict[str, "list[tuple[str, str]]"] = {
    "aot_865": [("geophysical_data", "aot_865")],
    "angstrom": [("geophysical_data", "angstrom")],
    "avw": [("geophysical_data", "avw")],
    "solar_zenith": [
        ("geophysical_data", "solar_zenith"),
        ("geophysical_data", "solz"),
        ("navigation_data", "solar_zenith"),
    ],
    "sensor_zenith": [
        ("geophysical_data", "sensor_zenith"),
        ("geophysical_data", "senz"),
        ("navigation_data", "sensor_zenith"),
    ],
    "relative_azimuth": [
        ("geophysical_data", "relative_azimuth"),
        ("geophysical_data", "relaz"),
        ("navigation_data", "relative_azimuth"),
    ],
    "wind_speed": [
        ("geophysical_data", "wind_speed"),
        ("meteorological_data", "wind_speed"),
        ("geophysical_data", "windspeed"),
    ],
}


def _to_float_filled(var) -> np.ndarray:
    """Read a netCDF4 Variable as a float array with masked/fill values
    converted to NaN."""
    data = var[:]
    if np.ma.isMaskedArray(data):
        return data.filled(np.nan).astype(float)
    return np.asarray(data, dtype=float)


class PaceOciL2Reader(SensorReader):
    """Reader for PACE OCI Level-2 OC_AOP granules."""

    sensor_name = "PACE-OCI"
    #: NASA cites "1 km spatial resolution at nadir"; more precise
    #: technical-paper figures range 1.05-1.2 km depending on source.
    #: Prefer the geometry-derived, per-match-up value in
    #: SpectralCube.pixel_size_km over this constant.
    nominal_pixel_size_m = 1000.0

    def __init__(self, path: str):
        super().__init__(path)
        self._ds = None

    # -- lifecycle -----------------------------------------------------
    def open(self) -> None:
        import netCDF4

        self._ds = netCDF4.Dataset(self.path, mode="r")
        self._ds.set_auto_mask(True)

    def close(self) -> None:
        if self._ds is not None:
            self._ds.close()
            self._ds = None

    @classmethod
    def matches(cls, path: str) -> bool:
        import netCDF4

        try:
            with netCDF4.Dataset(path, mode="r") as ds:
                instrument = str(getattr(ds, "instrument", "")).upper()
                platform = str(getattr(ds, "platform", "")).upper()
                title = str(getattr(ds, "title", "")).upper()
                return "OCI" in instrument and (
                    "PACE" in platform or "PACE" in title or "PACE" in instrument
                )
        except Exception:
            return False

    # -- internal helpers -------------------------------------------------
    def _require_group(self, name: str):
        if self._ds is None:
            raise RuntimeError("Reader is not open; use as a context manager")
        if name not in self._ds.groups:
            raise GranuleFormatError(f"Expected group '{name}' not found in {self.path}")
        return self._ds.groups[name]

    def _find_variable(self, candidates: "list[tuple[str, str]]"):
        for group_name, var_name in candidates:
            group = self._ds.groups.get(group_name)
            if group is not None and var_name in group.variables:
                return group.variables[var_name]
        return None

    # -- geolocation & time ----------------------------------------------
    def get_navigation(self):
        nav = self._require_group("navigation_data")
        if "longitude" not in nav.variables or "latitude" not in nav.variables:
            raise GranuleFormatError("navigation_data is missing longitude/latitude")
        lon = _to_float_filled(nav.variables["longitude"])
        lat = _to_float_filled(nav.variables["latitude"])
        return lon, lat

    def get_time_coverage(self):
        start = getattr(self._ds, "time_coverage_start", None)
        end = getattr(self._ds, "time_coverage_end", None)
        return start, end

    def get_scan_line_times(self) -> Optional[np.ndarray]:
        group = self._ds.groups.get("scan_line_attributes")
        if group is None:
            return None
        needed = ("year", "day", "msec")
        if not all(name in group.variables for name in needed):
            return None
        year = _to_float_filled(group.variables["year"])
        day = _to_float_filled(group.variables["day"])
        msec = _to_float_filled(group.variables["msec"])
        try:
            return time_utils.scan_line_times_from_yds(year, day, msec)
        except Exception:
            return None

    # -- spectral data ------------------------------------------------
    def get_wavelengths(self) -> np.ndarray:
        group = self._require_group("sensor_band_parameters")
        for name in ("wavelength_3d", "wavelength"):
            if name in group.variables:
                return _to_float_filled(group.variables[name])
        raise GranuleFormatError(
            "sensor_band_parameters is missing a wavelength variable "
            "(expected 'wavelength_3d' or 'wavelength')"
        )

    def get_rrs_cube(self) -> np.ndarray:
        geo = self._require_group("geophysical_data")
        if "Rrs" not in geo.variables:
            raise GranuleFormatError("geophysical_data is missing 'Rrs'")
        cube = _to_float_filled(geo.variables["Rrs"])
        if cube.ndim != 3:
            raise GranuleFormatError(
                f"Expected Rrs to be 3D (rows, cols, bands); got shape {cube.shape}"
            )
        return cube

    def get_quality_flags(self) -> np.ndarray:
        geo = self._require_group("geophysical_data")
        if "l2_flags" not in geo.variables:
            raise GranuleFormatError("geophysical_data is missing 'l2_flags'")
        var = geo.variables["l2_flags"]
        data = var[:]
        if np.ma.isMaskedArray(data):
            data = data.filled(0)
        return np.asarray(data, dtype=np.int64)

    def get_flag_name_to_bit(self) -> Optional[Dict[str, int]]:
        geo = self._require_group("geophysical_data")
        var = geo.variables.get("l2_flags")
        if var is None:
            return None
        flag_meanings = getattr(var, "flag_meanings", None)
        flag_masks = getattr(var, "flag_masks", None)
        if not flag_meanings or flag_masks is None:
            return None
        from ..core.flags import flag_meanings_to_bit_map

        try:
            return flag_meanings_to_bit_map(flag_meanings, flag_masks)
        except Exception:
            return None

    def get_atmospheric_products(self) -> Dict[str, np.ndarray]:
        out: Dict[str, np.ndarray] = {}
        for product_name, candidates in _ATMOSPHERIC_CANDIDATES.items():
            var = self._find_variable(candidates)
            if var is not None:
                out[product_name] = _to_float_filled(var)
        return out

    # -- metadata / provenance -------------------------------------------
    def get_platform_name(self) -> Optional[str]:
        return getattr(self._ds, "platform", None)

    def get_processing_version(self) -> Optional[str]:
        return getattr(self._ds, "processing_version", None)
