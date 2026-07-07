"""SpectralCube: the common result object returned for every sensor.

Per Anequim's design principles, every retrieval — regardless of which
satellite it came from — is returned as a SpectralCube carrying the same
fields: Rrs, wavelengths, navigation, atmospheric products, quality
flags, and full provenance. Downstream code (statistics, algorithms,
plotting) is written against this one object and therefore works
identically across sensors.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional

import numpy as np

from .provenance import Provenance
from .qc import QCResult


@dataclasses.dataclass
class SpectralCube:
    """Sensor-independent container for an Rrs (+ ancillary) retrieval.

    Attributes
    ----------
    sensor:
        Canonical sensor name, e.g. "PACE-OCI".
    wavelengths:
        Native center wavelengths (nm) of the bands included, shape (B,).
    rrs:
        Remote sensing reflectance pixel cube, shape (n_pixels, B),
        already flattened from whatever 2D ROI shape it came from, in
        the sensor's own native units (typically sr^-1). Pixels excluded
        by pixel-level QC are *not* removed from this array — see
        ``valid_mask`` — so the full spatial context is preserved.
    valid_mask:
        Boolean array, shape (n_pixels,); True where a pixel passed
        pixel-level quality control (unflagged, finite).
    longitude, latitude:
        Pixel-center coordinates, shape (n_pixels,), parallel to ``rrs``.
    quality_flags:
        Raw per-pixel quality-flag integers (e.g. OBPG ``l2_flags``),
        shape (n_pixels,), or ``None`` if not available.
    atmospheric:
        Dict of ancillary per-pixel atmospheric/geometry products (e.g.
        "aot_865", "angstrom", "solar_zenith", "sensor_zenith",
        "relative_azimuth", "wind_speed"), each shape (n_pixels,).
        Populated only when available in the source granule and
        ``RetrievalConfig.include_atmospheric`` is True.
    qc:
        :class:`~anequim.core.qc.QCResult` summarizing box-level QC and
        the representative (mean/median) spectrum.
    roi_shape:
        Original 2D shape (rows, cols) of the ROI before flattening, or
        ``None`` for non-rectangular ROIs (e.g. circular masks already
        applied).
    provenance:
        Full :class:`~anequim.core.provenance.Provenance` record.
    """

    sensor: str
    wavelengths: np.ndarray
    rrs: np.ndarray
    valid_mask: np.ndarray
    longitude: np.ndarray
    latitude: np.ndarray
    qc: QCResult
    provenance: Provenance
    quality_flags: Optional[np.ndarray] = None
    atmospheric: Dict[str, np.ndarray] = dataclasses.field(default_factory=dict)
    roi_shape: Optional[tuple] = None

    # -- basic shape/consistency checks -----------------------------------
    def __post_init__(self) -> None:
        self.wavelengths = np.asarray(self.wavelengths, dtype=float)
        self.rrs = np.asarray(self.rrs, dtype=float)
        self.valid_mask = np.asarray(self.valid_mask, dtype=bool)
        self.longitude = np.asarray(self.longitude, dtype=float)
        self.latitude = np.asarray(self.latitude, dtype=float)
        n_pixels, n_bands = self.rrs.shape
        if self.wavelengths.shape[0] != n_bands:
            raise ValueError(
                f"wavelengths length ({self.wavelengths.shape[0]}) != rrs bands ({n_bands})"
            )
        if self.valid_mask.shape[0] != n_pixels:
            raise ValueError("valid_mask length must match rrs n_pixels")
        if self.longitude.shape[0] != n_pixels or self.latitude.shape[0] != n_pixels:
            raise ValueError("longitude/latitude length must match rrs n_pixels")

    # -- convenience accessors ---------------------------------------------
    @property
    def n_pixels(self) -> int:
        return self.rrs.shape[0]

    @property
    def n_bands(self) -> int:
        return self.rrs.shape[1]

    @property
    def spectrum(self) -> np.ndarray:
        """Representative (mean or median, per QCConfig) Rrs spectrum."""
        return self.qc.spectrum

    @property
    def spectrum_std(self) -> np.ndarray:
        return self.qc.spectrum_std

    @property
    def pixel_size_km(self) -> Optional[Dict[str, float]]:
        """Actual ground pixel size measured from this granule's own
        geolocation grid at the matched location (see
        :mod:`anequim.geometry.pixel_size`) — ``None`` if unavailable."""
        return self.provenance.pixel_size_km

    @property
    def roi_footprint_km(self) -> Optional[Dict[str, float]]:
        """Overall footprint of the selected ROI, measured the same way
        — ``None`` if unavailable."""
        return self.provenance.roi_footprint_km

    def is_reliable(self) -> bool:
        """True if the ROI passed the minimum valid-fraction requirement
        AND was judged spatially homogeneous (see QCConfig.max_cv)."""
        return bool(self.qc.passed_valid_fraction and self.qc.homogeneous)

    # -- export --------------------------------------------------------
    def spectrum_dataframe(self):
        """Per-wavelength representative spectrum as a pandas DataFrame
        with columns: wavelength, rrs, rrs_std, n_used, cv."""
        import pandas as pd

        return pd.DataFrame(
            {
                "wavelength_nm": self.wavelengths,
                "rrs": self.qc.spectrum,
                "rrs_std": self.qc.spectrum_std,
                "n_used": self.qc.n_used,
                "cv": self.qc.cv_per_band,
            }
        )

    def pixel_dataframe(self):
        """Full per-pixel table (one row per pixel, one column per band
        plus navigation/flags/atmospheric products) as a pandas
        DataFrame — useful for custom diagnostics."""
        import pandas as pd

        data: Dict[str, Any] = {
            "longitude": self.longitude,
            "latitude": self.latitude,
            "valid": self.valid_mask,
        }
        if self.quality_flags is not None:
            data["quality_flags"] = self.quality_flags
        for name, arr in self.atmospheric.items():
            data[name] = arr
        for i, wl in enumerate(self.wavelengths):
            data[f"rrs_{wl:.1f}nm"] = self.rrs[:, i]
        return pd.DataFrame(data)

    def summary(self) -> Dict[str, Any]:
        """A flat dict combining QC and provenance, handy for logging or
        a single-row summary table across many match-ups."""
        out: Dict[str, Any] = {"sensor": self.sensor, "n_bands": self.n_bands}
        out.update(self.qc.summary())
        out["acquisition_time"] = self.provenance.acquisition_time
        out["target_time"] = self.provenance.target_time
        out["target_longitude"] = self.provenance.target_longitude
        out["target_latitude"] = self.provenance.target_latitude
        out["roi_description"] = self.provenance.roi_description
        out["pixel_size_km"] = self.provenance.pixel_size_km
        out["roi_footprint_km"] = self.provenance.roi_footprint_km
        out["reliable"] = self.is_reliable()
        return out

    def to_csv(self, path: str, kind: str = "spectrum") -> None:
        """Write either the representative ``spectrum`` (default) or the
        full ``pixel`` table to CSV."""
        if kind == "spectrum":
            self.spectrum_dataframe().to_csv(path, index=False)
        elif kind == "pixel":
            self.pixel_dataframe().to_csv(path, index=False)
        else:
            raise ValueError("kind must be 'spectrum' or 'pixel'")

    def to_xarray(self):
        """Optional export to an ``xarray.Dataset`` (requires xarray).
        Retains the full pixel cube, navigation, flags, atmospheric
        products, and provenance as dataset attributes.
        """
        try:
            import xarray as xr
        except ImportError as exc:  # pragma: no cover - exercised only without xarray
            raise ImportError(
                "xarray is required for to_xarray(); install anequim[xarray]"
            ) from exc

        data_vars = {
            "rrs": (("pixel", "wavelength"), self.rrs),
            "valid_mask": (("pixel",), self.valid_mask),
            "longitude": (("pixel",), self.longitude),
            "latitude": (("pixel",), self.latitude),
        }
        if self.quality_flags is not None:
            data_vars["quality_flags"] = (("pixel",), self.quality_flags)
        for name, arr in self.atmospheric.items():
            data_vars[name] = (("pixel",), arr)

        ds = xr.Dataset(
            data_vars=data_vars,
            coords={"wavelength": self.wavelengths, "pixel": np.arange(self.n_pixels)},
            attrs={"sensor": self.sensor, **{f"prov_{k}": str(v) for k, v in self.provenance.as_dict().items()}},
        )
        return ds

    def __repr__(self) -> str:
        return (
            f"SpectralCube(sensor={self.sensor!r}, n_pixels={self.n_pixels}, "
            f"n_bands={self.n_bands}, valid_fraction={self.qc.valid_fraction:.2f}, "
            f"reliable={self.is_reliable()})"
        )
