"""Configuration objects controlling retrieval and quality control.

Default numeric thresholds follow common practice in ocean color cal/val
(Bailey & Werdell, 2006 and related OB.DAAC / AERONET-OC match-up work).
They are sensible defaults, not universal constants: always confirm
against whatever specific protocol you are trying to reproduce.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from typing import Iterable, Optional, Sequence, Union

TimeLike = Union[str, _dt.datetime]
UTC = _dt.timezone.utc


def parse_time(value: TimeLike) -> _dt.datetime:
    """Parse an ISO-8601 string (trailing 'Z' accepted) or ``datetime``
    into a timezone-aware UTC ``datetime``."""
    if isinstance(value, _dt.datetime):
        dt = value
    else:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = _dt.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


@dataclasses.dataclass
class QCConfig:
    """Pixel- and box-level quality-control thresholds.

    Parameters
    ----------
    flag_names:
        Names of quality-flag bits (as given by each granule's own
        ``flag_meanings`` attribute) that disqualify a pixel outright. If
        ``None``, each reader supplies a literature-typical default
        exclusion set for its sensor.
    min_valid_fraction:
        Minimum fraction of unflagged, finite pixels required within an
        ROI for a retrieval to be considered usable. Bailey & Werdell
        (2006)-style protocols commonly require at least half the pixels
        in a match-up box to be valid.
    max_cv:
        Maximum allowed coefficient of variation (population std / mean)
        of valid pixel values, used as a spatial-homogeneity check. ROIs
        exceeding this are flagged ``homogeneous=False`` but are *not*
        silently discarded — the caller decides.
    cv_reduction:
        How per-band CV values are reduced to a single pass/fail check:
        "any", "mean", or "median" across bands.
    min_signal_for_cv:
        If given, bands whose |mean valid-pixel value| falls below this
        threshold are excluded from the coefficient-of-variation
        homogeneity check (though still reported normally in the output
        spectrum/std). This guards against near-zero-signal bands (e.g.
        the far red/NIR edge of an Rrs spectrum, or a deep absorption
        feature) producing spuriously huge CV values simply because they
        divide by a near-zero mean — which would otherwise dominate
        "mean"/"median" reductions across bands and mark an otherwise
        homogeneous ROI as unreliable. Leave ``None`` (the default) to
        include every band in the CV check, matching prior behavior.
    center_statistic:
        "mean" or "median" — how the representative spectrum for an ROI
        is computed from its valid pixels.
    exclude_outliers:
        If True, trim pixels further than ``outlier_n_std`` standard
        deviations from the ROI mean (per band) before computing the
        representative statistic.
    outlier_n_std:
        Standard-deviation multiple used by ``exclude_outliers``.
    """

    flag_names: Optional[Sequence[str]] = None
    min_valid_fraction: float = 0.5
    max_cv: float = 0.15
    cv_reduction: str = "mean"
    min_signal_for_cv: Optional[float] = None
    center_statistic: str = "mean"
    exclude_outliers: bool = False
    outlier_n_std: float = 1.5

    def __post_init__(self) -> None:
        if not (0.0 <= self.min_valid_fraction <= 1.0):
            raise ValueError("min_valid_fraction must be within [0, 1]")
        if self.max_cv < 0:
            raise ValueError("max_cv must be non-negative")
        if self.cv_reduction not in ("any", "mean", "median"):
            raise ValueError("cv_reduction must be 'any', 'mean', or 'median'")
        if self.min_signal_for_cv is not None and self.min_signal_for_cv < 0:
            raise ValueError("min_signal_for_cv must be non-negative")
        if self.center_statistic not in ("mean", "median"):
            raise ValueError("center_statistic must be 'mean' or 'median'")
        if self.outlier_n_std <= 0:
            raise ValueError("outlier_n_std must be positive")


@dataclasses.dataclass
class RetrievalConfig:
    """Top-level configuration for a single-point or ROI Rrs retrieval.

    Parameters
    ----------
    longitude, latitude:
        Target location in decimal degrees (used directly for point/
        circular/rectangular ROIs; ignored if an explicit polygon or
        bounding box ROI object is passed instead).
    target_time:
        Target time as an ISO-8601 string or ``datetime``. Naive
        datetimes are assumed UTC.
    time_window_hours:
        Half-width, in hours, of the acceptance window around
        ``target_time``. Default +/-3 h follows common cal/val practice.
    box_size:
        Side length, in pixels, of the default square ROI used when no
        explicit ROI object is supplied. Must be odd and >= 1.
    max_search_radius_km:
        Sanity-check radius: if the nearest pixel found in a granule is
        farther than this from the target point, the granule is treated
        as not covering the point.
    qc:
        Nested :class:`QCConfig`.
    wavelengths:
        Optional subset of wavelengths (nm) to keep. ``None`` keeps every
        native band the sensor provides (no interpolation is ever done
        implicitly — see :mod:`anequim.harmonization`).
    wavelength_tolerance_nm:
        Maximum allowed distance between a requested wavelength and the
        nearest available native band.
    include_atmospheric:
        Whether to also retrieve ancillary atmospheric products (AOT,
        Angstrom exponent, solar/sensor zenith, relative azimuth, wind
        speed) alongside Rrs, when the reader/granule provides them.
    """

    longitude: float
    latitude: float
    target_time: TimeLike
    time_window_hours: float = 3.0
    box_size: int = 5
    max_search_radius_km: float = 15.0
    qc: QCConfig = dataclasses.field(default_factory=QCConfig)
    wavelengths: Optional[Iterable[float]] = None
    wavelength_tolerance_nm: float = 2.5
    include_atmospheric: bool = True

    def __post_init__(self) -> None:
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError("longitude must be within [-180, 180]")
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError("latitude must be within [-90, 90]")
        if self.box_size < 1 or self.box_size % 2 == 0:
            raise ValueError("box_size must be a positive odd integer")
        if self.time_window_hours <= 0:
            raise ValueError("time_window_hours must be positive")
        if self.max_search_radius_km <= 0:
            raise ValueError("max_search_radius_km must be positive")
        if self.wavelengths is not None:
            self.wavelengths = list(self.wavelengths)
        self._target_time_dt = parse_time(self.target_time)

    @property
    def target_time_dt(self) -> _dt.datetime:
        return self._target_time_dt

    @property
    def half_window(self) -> _dt.timedelta:
        return _dt.timedelta(hours=self.time_window_hours)

    @property
    def box_radius(self) -> int:
        return self.box_size // 2
