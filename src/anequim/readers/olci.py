"""Reader for Sentinel-3 OLCI Level-2 ``OL_2_WFR`` (water full resolution)
products.

Unlike PACE OCI/MODIS/VIIRS (one grouped NetCDF file per granule), an
OLCI L2 WFR granule is a **directory** (ESA SAFE format,
``S3?_OL_2_WFR____....SEN3``) containing ~20-30 separate NetCDF files.
The ones this reader uses:

- ``xfdumanifest.xml`` — SAFE manifest; its presence is what
  :func:`anequim.utils.file_discovery.resolve_files` uses to treat the
  whole directory as one granule rather than a folder of files.
- ``geo_coordinates.nc`` — ``longitude``, ``latitude`` (2D, full
  resolution, dims typically ``rows`` x ``columns``); also carries the
  granule's ``start_time``/``stop_time`` global attributes.
- ``Oa01_reflectance.nc`` ... ``Oa21_reflectance.nc`` — one file per
  spectral band, variable named e.g. ``Oa01_reflectance``. Bands
  dedicated to atmospheric gas absorption (Oa13-Oa15, Oa19-Oa20) are not
  meaningful water-leaving/Rrs products and are skipped, leaving the 16
  usable bands.
- ``wqsf.nc`` — ``WQSF``, the per-pixel Water Quality and Science Flags,
  with its own ``flag_meanings``/``flag_masks`` attributes (same style
  as OBPG's ``l2_flags``, so :mod:`anequim.core.flags` handles it
  generically via those attributes).

Units handling (important): EUMETSAT's Collection 4 reprocessing
(effective 26 Feb 2026) switched the per-band product from water-leaving
reflectance rho_w to remote sensing reflectance Rrs directly
(Rrs = rho_w / pi), and processing continues to evolve. Rather than
assume a fixed convention, this reader checks each band variable's own
``units`` attribute and only divides by pi when it does *not* already
indicate Rrs (i.e. units are dimensionless / "1", the rho_w convention),
so files from either processing baseline are handled correctly.

Known limitations of this implementation
-----------------------------------------
- Per-pixel solar/sensor geometry (``tie_geometries.nc``) is provided on
  a coarser "tie-point" grid than the full-resolution Rrs/geolocation
  grid and would need interpolation to line up pixel-for-pixel; that
  interpolation is not implemented yet, so
  :meth:`get_atmospheric_products` does not currently return
  geometry/meteorology fields for OLCI (it returns whatever full-
  resolution products it can find, which may be an empty dict for some
  granules). AOT/Angstrom (``w_aer.nc``, full resolution) are read when
  present.
- The default flag-exclusion set in :meth:`get_default_excluded_flags`
  is a reasonable, literature-typical starting point for WQSF, not a
  verbatim reproduction of any single EUMETSAT-recommended table —
  check it against your own file's ``flag_meanings`` and override
  ``QCConfig.flag_names`` for rigorous work.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

import numpy as np

from ..core.exceptions import GranuleFormatError
from .base import SensorReader

# Standard OLCI band table: (file band number, center wavelength nm).
# Bands 13-15 and 19-20 are atmospheric-gas-absorption bands with no
# meaningful water-leaving reflectance/Rrs product and are excluded.
_ALL_OLCI_BANDS = {
    1: 400.0, 2: 412.5, 3: 442.5, 4: 490.0, 5: 510.0, 6: 560.0, 7: 620.0,
    8: 665.0, 9: 673.75, 10: 681.25, 11: 708.75, 12: 753.75, 13: 761.25,
    14: 764.375, 15: 767.5, 16: 778.75, 17: 865.0, 18: 885.0, 19: 900.0,
    20: 940.0, 21: 1020.0,
}
_GAS_ABSORPTION_BANDS = {13, 14, 15, 19, 20}
OLCI_RRS_BANDS = {n: wl for n, wl in _ALL_OLCI_BANDS.items() if n not in _GAS_ABSORPTION_BANDS}

#: A reasonable, literature-typical starting set of WQSF flags to
#: exclude for open-ocean Rrs work. Not a verbatim reproduction of any
#: single EUMETSAT table (see module docstring) — verify against your
#: own granule's flag_meanings for rigorous use.
DEFAULT_OLCI_EXCLUDED_FLAGS = (
    "CLOUD",
    "CLOUD_AMBIGUOUS",
    "CLOUD_MARGIN",
    "INVALID",
    "COSMETIC",
    "SATURATED",
    "SUSPECT",
    "HISOLZEN",
    "HIGHGLINT",
    "SNOW_ICE",
    "AC_FAIL",
    "WHITECAPS",
    "LAND",
)


def _to_float_filled(var) -> np.ndarray:
    data = var[:]
    if np.ma.isMaskedArray(data):
        return data.filled(np.nan).astype(float)
    return np.asarray(data, dtype=float)


class OlciL2Reader(SensorReader):
    """Reader for Sentinel-3 OLCI Level-2 WFR granules (directory-based)."""

    sensor_name = "Sentinel3-OLCI"
    #: OLCI full-resolution water products are nominally 300 m at nadir.
    nominal_pixel_size_m = 300.0

    def __init__(self, path: str):
        super().__init__(path)
        self._datasets: Dict[str, "object"] = {}
        self._band_numbers: Optional[list] = None

    # -- lifecycle -----------------------------------------------------
    def open(self) -> None:
        if not os.path.isdir(self.path):
            raise GranuleFormatError(
                f"Expected an OLCI SAFE granule directory, got a non-directory path: {self.path}"
            )
        self._datasets = {}

    def close(self) -> None:
        for ds in self._datasets.values():
            try:
                ds.close()
            except Exception:
                pass
        self._datasets = {}

    def _dataset(self, filename: str):
        """Lazily open (and cache) one component NetCDF file by name."""
        if filename not in self._datasets:
            import netCDF4

            full_path = os.path.join(self.path, filename)
            if not os.path.isfile(full_path):
                raise GranuleFormatError(f"Expected file '{filename}' not found in {self.path}")
            ds = netCDF4.Dataset(full_path, mode="r")
            ds.set_auto_mask(True)
            self._datasets[filename] = ds
        return self._datasets[filename]

    @classmethod
    def matches(cls, path: str) -> bool:
        if not os.path.isdir(path):
            return False
        required = ("xfdumanifest.xml", "geo_coordinates.nc", "wqsf.nc")
        if not all(os.path.isfile(os.path.join(path, name)) for name in required):
            return False
        # At least one usable Rrs band file should be present.
        return any(
            os.path.isfile(os.path.join(path, f"Oa{n:02d}_reflectance.nc"))
            for n in OLCI_RRS_BANDS
        )

    # -- available bands (depends on which band files actually exist) ----
    def _available_band_numbers(self) -> list:
        if self._band_numbers is None:
            self._band_numbers = [
                n for n in sorted(OLCI_RRS_BANDS)
                if os.path.isfile(os.path.join(self.path, f"Oa{n:02d}_reflectance.nc"))
            ]
            if not self._band_numbers:
                raise GranuleFormatError(f"No usable Oa##_reflectance.nc files found in {self.path}")
        return self._band_numbers

    # -- geolocation & time ----------------------------------------------
    def get_navigation(self):
        ds = self._dataset("geo_coordinates.nc")
        if "longitude" not in ds.variables or "latitude" not in ds.variables:
            raise GranuleFormatError("geo_coordinates.nc is missing longitude/latitude")
        lon = _to_float_filled(ds.variables["longitude"])
        lat = _to_float_filled(ds.variables["latitude"])
        return lon, lat

    def get_time_coverage(self):
        # start_time/stop_time are standard ESA global attributes present
        # on every OLCI L1/L2 component NetCDF file.
        for filename in ("geo_coordinates.nc", "wqsf.nc"):
            try:
                ds = self._dataset(filename)
            except GranuleFormatError:
                continue
            start = getattr(ds, "start_time", None)
            stop = getattr(ds, "stop_time", None)
            if start or stop:
                return start, stop
        return None, None

    # -- spectral data ------------------------------------------------
    def get_wavelengths(self) -> np.ndarray:
        return np.array([OLCI_RRS_BANDS[n] for n in self._available_band_numbers()], dtype=float)

    def get_rrs_cube(self) -> np.ndarray:
        band_numbers = self._available_band_numbers()
        bands = []
        for n in band_numbers:
            ds = self._dataset(f"Oa{n:02d}_reflectance.nc")
            var_name = f"Oa{n:02d}_reflectance"
            if var_name not in ds.variables:
                raise GranuleFormatError(f"Oa{n:02d}_reflectance.nc is missing variable '{var_name}'")
            var = ds.variables[var_name]
            values = _to_float_filled(var)
            units = str(getattr(var, "units", "")).strip().lower()
            # Collection 4+: units already sr-1 (Rrs). Earlier baselines:
            # dimensionless water-leaving reflectance rho_w; convert.
            already_rrs = units in ("sr-1", "sr^-1", "per steradian") or "sr-1" in units
            if not already_rrs:
                values = values / np.pi
            bands.append(values)
        return np.stack(bands, axis=-1)

    def get_quality_flags(self) -> np.ndarray:
        ds = self._dataset("wqsf.nc")
        if "WQSF" not in ds.variables:
            raise GranuleFormatError("wqsf.nc is missing variable 'WQSF'")
        data = ds.variables["WQSF"][:]
        if np.ma.isMaskedArray(data):
            data = data.filled(0)
        return np.asarray(data, dtype=np.int64)

    def get_flag_name_to_bit(self) -> Optional[Dict[str, int]]:
        ds = self._dataset("wqsf.nc")
        var = ds.variables.get("WQSF")
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

    def get_default_excluded_flags(self):
        return DEFAULT_OLCI_EXCLUDED_FLAGS

    def get_atmospheric_products(self) -> Dict[str, np.ndarray]:
        out: Dict[str, np.ndarray] = {}
        # Full-resolution aerosol product, when present.
        aer_path = os.path.join(self.path, "w_aer.nc")
        if os.path.isfile(aer_path):
            try:
                ds = self._dataset("w_aer.nc")
                for var_name, out_name in (("T865", "aot_865"), ("A865", "angstrom")):
                    if var_name in ds.variables:
                        out[out_name] = _to_float_filled(ds.variables[var_name])
            except Exception:
                pass
        # Solar/sensor geometry lives on a coarser tie-point grid in
        # tie_geometries.nc and is not interpolated to full resolution
        # yet — see module docstring "Known limitations".
        return out

    # -- metadata / provenance -------------------------------------------
    def get_platform_name(self) -> Optional[str]:
        try:
            ds = self._dataset("geo_coordinates.nc")
        except GranuleFormatError:
            return None
        for attr in ("platform", "source"):
            value = getattr(ds, attr, None)
            if value:
                return str(value)
        return None

    def get_processing_version(self) -> Optional[str]:
        try:
            ds = self._dataset("geo_coordinates.nc")
        except GranuleFormatError:
            return None
        for attr in ("references", "product_name", "history"):
            value = getattr(ds, attr, None)
            if value:
                return str(value)
        return None
