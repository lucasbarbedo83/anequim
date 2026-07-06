"""ROI-level quality control: valid-fraction checks, spatial homogeneity
(coefficient of variation), outlier trimming, and the representative
(mean/median) spectrum computation.

This implements the box-level half of the Bailey & Werdell (2006)-style
match-up protocol; :mod:`anequim.core.flags` implements the pixel-level
half (which pixels are disqualified outright by processing flags).
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import numpy as np

from .config import QCConfig
from .exceptions import InsufficientValidFractionError, NoValidPixelsError


@dataclasses.dataclass
class QCResult:
    """Outcome of applying :class:`QCConfig` to an ROI's pixel values.

    Attributes
    ----------
    n_total:
        Total number of pixels in the ROI (before any QC).
    n_valid:
        Number of pixels that passed flag-masking and finiteness checks.
    valid_fraction:
        ``n_valid / n_total``.
    cv_per_band:
        Coefficient of variation (std / |mean|) of valid pixels, per band.
    cv_reduced:
        Single scalar summarizing ``cv_per_band`` per ``cv_reduction``.
    homogeneous:
        Whether ``cv_reduced <= max_cv``.
    passed_valid_fraction:
        Whether ``valid_fraction >= min_valid_fraction``.
    spectrum:
        Representative Rrs spectrum (mean or median of valid, optionally
        outlier-trimmed pixels), shape (n_bands,).
    spectrum_std:
        Per-band standard deviation of the pixels used for ``spectrum``.
    n_used:
        Number of pixels actually used to compute ``spectrum`` (after any
        outlier trimming), per band.
    """

    n_total: int
    n_valid: int
    valid_fraction: float
    cv_per_band: np.ndarray
    cv_reduced: float
    homogeneous: bool
    passed_valid_fraction: bool
    spectrum: np.ndarray
    spectrum_std: np.ndarray
    n_used: np.ndarray

    def summary(self) -> dict:
        return {
            "n_total": self.n_total,
            "n_valid": self.n_valid,
            "valid_fraction": round(self.valid_fraction, 4),
            "cv_reduced": round(float(self.cv_reduced), 4) if np.isfinite(self.cv_reduced) else None,
            "homogeneous": self.homogeneous,
            "passed_valid_fraction": self.passed_valid_fraction,
        }


def _reduce_cv(cv_per_band: np.ndarray, method: str) -> float:
    finite = cv_per_band[np.isfinite(cv_per_band)]
    if finite.size == 0:
        return float("nan")
    if method == "any":
        return float(np.max(finite))
    if method == "median":
        return float(np.median(finite))
    return float(np.mean(finite))


def _trim_outliers(values: np.ndarray, valid: np.ndarray, n_std: float) -> np.ndarray:
    """Return an updated validity mask with per-band outlier pixels
    (beyond ``n_std`` standard deviations from the valid-pixel mean)
    additionally excluded. ``values`` has shape (n_pixels, n_bands);
    ``valid`` has shape (n_pixels,) and is broadcast across bands.
    """
    out_valid = valid.copy()
    for b in range(values.shape[1]):
        col = values[:, b]
        mask = valid & np.isfinite(col)
        if mask.sum() < 2:
            continue
        mean = col[mask].mean()
        std = col[mask].std()
        if std == 0 or not np.isfinite(std):
            continue
        band_outlier = mask & (np.abs(col - mean) > n_std * std)
        out_valid &= ~band_outlier
    return out_valid


def evaluate_roi(
    values: np.ndarray,
    valid_mask: np.ndarray,
    qc: QCConfig,
    raise_on_failure: bool = False,
) -> QCResult:
    """Apply box-level QC to an ROI's pixel values for one product
    (typically Rrs, but usable for any per-band array).

    Parameters
    ----------
    values:
        Array of shape (n_pixels, n_bands) — pixel values already
        flattened from whatever 2D box/ROI shape they came from.
    valid_mask:
        Boolean array of shape (n_pixels,), True where a pixel passed
        pixel-level flag masking (see :mod:`anequim.core.flags`) *before*
        any additional finiteness/outlier screening.
    qc:
        Thresholds to apply.
    raise_on_failure:
        If True, raise :class:`NoValidPixelsError` /
        :class:`InsufficientValidFractionError` instead of returning a
        QCResult with ``passed_valid_fraction=False``.
    """
    values = np.asarray(values, dtype=float)
    valid_mask = np.asarray(valid_mask, dtype=bool)
    n_total = values.shape[0]
    if n_total == 0:
        raise NoValidPixelsError("ROI contains zero pixels")

    finite_mask = np.all(np.isfinite(values), axis=1)
    valid = valid_mask & finite_mask
    n_valid = int(valid.sum())
    valid_fraction = n_valid / n_total if n_total else 0.0

    if n_valid == 0:
        if raise_on_failure:
            raise NoValidPixelsError("No pixels passed flag masking and finiteness checks")
        n_bands = values.shape[1]
        nan_spec = np.full(n_bands, np.nan)
        return QCResult(
            n_total=n_total,
            n_valid=0,
            valid_fraction=0.0,
            cv_per_band=nan_spec.copy(),
            cv_reduced=float("nan"),
            homogeneous=False,
            passed_valid_fraction=False,
            spectrum=nan_spec.copy(),
            spectrum_std=nan_spec.copy(),
            n_used=np.zeros(n_bands, dtype=int),
        )

    passed_fraction = valid_fraction >= qc.min_valid_fraction
    if raise_on_failure and not passed_fraction:
        raise InsufficientValidFractionError(
            f"valid_fraction={valid_fraction:.3f} < min_valid_fraction={qc.min_valid_fraction:.3f}"
        )

    use_mask = valid
    if qc.exclude_outliers:
        use_mask = _trim_outliers(values, valid, qc.outlier_n_std)
        if use_mask.sum() == 0:
            use_mask = valid  # outlier trimming ate everything; fall back

    used_values = values[use_mask]
    with np.errstate(invalid="ignore", divide="ignore"):
        band_mean = np.nanmean(used_values, axis=0)
        band_std = np.nanstd(used_values, axis=0)
        band_median = np.nanmedian(used_values, axis=0)
        cv_per_band = np.where(band_mean != 0, band_std / np.abs(band_mean), np.nan)

    cv_reduced = _reduce_cv(cv_per_band, qc.cv_reduction)
    homogeneous = np.isfinite(cv_reduced) and cv_reduced <= qc.max_cv

    spectrum = band_mean if qc.center_statistic == "mean" else band_median
    n_used = np.full(values.shape[1], int(use_mask.sum()), dtype=int)

    return QCResult(
        n_total=n_total,
        n_valid=n_valid,
        valid_fraction=valid_fraction,
        cv_per_band=cv_per_band,
        cv_reduced=cv_reduced,
        homogeneous=bool(homogeneous),
        passed_valid_fraction=bool(passed_fraction),
        spectrum=spectrum,
        spectrum_std=band_std,
        n_used=n_used,
    )
