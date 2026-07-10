"""Shared implementation for "classic" OBPG multiband Level-2 ocean color
files — the format used by MODIS (Aqua/Terra) and VIIRS (SNPP/NOAA-20/
NOAA-21) L2 OC products.

This format differs from PACE OCI's in one structurally important way,
confirmed against NASA's own Ocean Level-2 Data Format Specification
(oceancolor.gsfc.nasa.gov/resources/docs/format/l2nc/): *"Parameters
that are wavelength-specific (e.g., Rrs) have separate data objects for
each band"* — i.e. ``geophysical_data`` holds separate variables like
``Rrs_412``, ``Rrs_443``, ``Rrs_469``, ... rather than PACE's single 3D
hyperspectral ``Rrs`` array with a ``wavelength_3d`` dimension.

Everything else (``navigation_data`` longitude/latitude,
``geophysical_data/l2_flags`` with the standard OBPG bit layout,
``scan_line_attributes`` year/day/msec, global attributes) follows the
same shared OBPG multi-mission convention as PACE OCI, so this base
class reuses that logic and only handles the per-band-variable Rrs
assembly differently.

Rather than hardcode a band list per sensor/platform (MODIS-Aqua vs.
Terra, or VIIRS-SNPP vs. NOAA-20/21, have slightly different center
wavelengths), this reader discovers whichever ``Rrs_<number>`` variables
actually exist in a given file and uses their numeric suffixes as the
wavelengths directly — robust to those small cross-platform differences
without needing a lookup table.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import numpy as np

from ..core.exceptions import GranuleFormatError
from .base import SensorReader

_RRS_VAR_PATTERN = re.compile(r"^Rrs_(\d+)$")


def _to_float_filled(var) -> np.ndarray:
    data = var[:]
    if np.ma.isMaskedArray(data):
        return data.filled(np.nan).astype(float)
    return np.asarray(data, dtype=float)


class ObpgMultibandL2Reader(SensorReader):
    """Base class for classic OBPG multiband L2 ocean color readers
    (MODIS, VIIRS). Subclasses set ``sensor_name``,
    ``nominal_pixel_size_m``, and implement ``matches()``.
    """

    def __init__(self, path: str):
        super().__init__(path)
        self._ds = None
        self._rrs_band_numbers: Optional[List[int]] = None

    # -- lifecycle -----------------------------------------------------
    def open(self) -> None:
        import netCDF4

        self._ds = netCDF4.Dataset(self.path, mode="r")
        self._ds.set_auto_mask(True)

    def close(self) -> None:
        if self._ds is not None:
            self._ds.close()
            self._ds = None

    def _require_group(self, name: str):
        if self._ds is None:
            raise RuntimeError("Reader is not open; use as a context manager")
        if name not in self._ds.groups:
            raise GranuleFormatError(f"Expected group '{name}' not found in {self.path}")
        return self._ds.groups[name]

    # -- band discovery ---------------------------------------------------
    def _discover_rrs_bands(self) -> List[int]:
        if self._rrs_band_numbers is None:
            geo = self._require_group("geophysical_data")
            bands = []
            for name in geo.variables:
                match = _RRS_VAR_PATTERN.match(name)
                if match:
                    bands.append(int(match.group(1)))
            if not bands:
                raise GranuleFormatError(
                    f"No Rrs_<wavelength> variables found in geophysical_data of {self.path}"
                )
            self._rrs_band_numbers = sorted(bands)
        return self._rrs_band_numbers

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
        from ..core import time_utils

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
        return np.array(self._discover_rrs_bands(), dtype=float)

    def get_rrs_cube(self) -> np.ndarray:
        geo = self._require_group("geophysical_data")
        bands = self._discover_rrs_bands()
        stacks = []
        for band in bands:
            var_name = f"Rrs_{band}"
            stacks.append(_to_float_filled(geo.variables[var_name]))
        return np.stack(stacks, axis=-1)

    def get_quality_flags(self) -> np.ndarray:
        geo = self._require_group("geophysical_data")
        if "l2_flags" not in geo.variables:
            raise GranuleFormatError("geophysical_data is missing 'l2_flags'")
        data = geo.variables["l2_flags"][:]
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
        # Falling back to the generic OBPG default table (see
        # get_default_excluded_flags returning None) is correct here,
        # since MODIS/VIIRS share PACE OCI's l2_flags bit layout.

    def get_atmospheric_products(self) -> Dict[str, np.ndarray]:
        geo = self._require_group("geophysical_data")
        out: Dict[str, np.ndarray] = {}
        candidates = {
            "aot_865": ("aot_865", "aot_869", "taua_869"),
            "angstrom": ("angstrom",),
            "solar_zenith": ("solz",),
            "sensor_zenith": ("senz",),
            "relative_azimuth": ("relaz",),
            "wind_speed": ("wind_speed", "windspeed"),
        }
        for out_name, var_names in candidates.items():
            for var_name in var_names:
                if var_name in geo.variables:
                    out[out_name] = _to_float_filled(geo.variables[var_name])
                    break
        return out

    # -- metadata / provenance -------------------------------------------
    def get_platform_name(self) -> Optional[str]:
        return getattr(self._ds, "platform", None)

    def get_processing_version(self) -> Optional[str]:
        return getattr(self._ds, "processing_version", None)
