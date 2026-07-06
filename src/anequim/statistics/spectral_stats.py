"""Spectral statistics computed over a :class:`~anequim.core.spectral_cube.SpectralCube`.

These operate on the full per-pixel cube (``cube.rrs``), independent of
whichever representative statistic (mean/median) was already baked into
``cube.qc.spectrum`` during retrieval — useful when you want a different
statistic, a percentile, or cross-band covariance/correlation for
uncertainty analysis.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..core.spectral_cube import SpectralCube


def _valid_values(cube: SpectralCube, use_valid_only: bool) -> np.ndarray:
    if use_valid_only:
        values = cube.rrs[cube.valid_mask]
    else:
        values = cube.rrs
    return values


def mean_spectrum(cube: SpectralCube, use_valid_only: bool = True) -> np.ndarray:
    """Per-band arithmetic mean, shape (n_bands,)."""
    values = _valid_values(cube, use_valid_only)
    if values.shape[0] == 0:
        return np.full(cube.n_bands, np.nan)
    return np.nanmean(values, axis=0)


def median_spectrum(cube: SpectralCube, use_valid_only: bool = True) -> np.ndarray:
    """Per-band median, shape (n_bands,)."""
    values = _valid_values(cube, use_valid_only)
    if values.shape[0] == 0:
        return np.full(cube.n_bands, np.nan)
    return np.nanmedian(values, axis=0)


def std_spectrum(cube: SpectralCube, use_valid_only: bool = True, ddof: int = 0) -> np.ndarray:
    """Per-band standard deviation, shape (n_bands,)."""
    values = _valid_values(cube, use_valid_only)
    if values.shape[0] == 0:
        return np.full(cube.n_bands, np.nan)
    return np.nanstd(values, axis=0, ddof=ddof)


def percentile_spectrum(
    cube: SpectralCube, q: float, use_valid_only: bool = True
) -> np.ndarray:
    """Per-band percentile (``q`` in [0, 100]), shape (n_bands,)."""
    if not (0.0 <= q <= 100.0):
        raise ValueError("q must be within [0, 100]")
    values = _valid_values(cube, use_valid_only)
    if values.shape[0] == 0:
        return np.full(cube.n_bands, np.nan)
    return np.nanpercentile(values, q, axis=0)


def coefficient_of_variation(cube: SpectralCube, use_valid_only: bool = True) -> np.ndarray:
    """Per-band coefficient of variation (std / |mean|), shape (n_bands,)."""
    mean = mean_spectrum(cube, use_valid_only)
    std = std_spectrum(cube, use_valid_only)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(mean != 0, std / np.abs(mean), np.nan)


def covariance_matrix(cube: SpectralCube, use_valid_only: bool = True) -> np.ndarray:
    """Band-by-band covariance matrix across pixels, shape (n_bands, n_bands).

    Rows with any NaN are dropped before computing covariance (i.e. only
    pixels with a complete spectrum contribute).
    """
    values = _valid_values(cube, use_valid_only)
    complete = values[np.all(np.isfinite(values), axis=1)]
    if complete.shape[0] < 2:
        return np.full((cube.n_bands, cube.n_bands), np.nan)
    return np.cov(complete, rowvar=False)


def correlation_matrix(cube: SpectralCube, use_valid_only: bool = True) -> np.ndarray:
    """Band-by-band Pearson correlation matrix, shape (n_bands, n_bands)."""
    values = _valid_values(cube, use_valid_only)
    complete = values[np.all(np.isfinite(values), axis=1)]
    if complete.shape[0] < 2:
        return np.full((cube.n_bands, cube.n_bands), np.nan)
    return np.corrcoef(complete, rowvar=False)


def summary_table(cube: SpectralCube, use_valid_only: bool = True):
    """A pandas DataFrame with one row per wavelength and columns for
    mean, median, std, cv, p10, p90, and n_valid — a quick multi-statistic
    view beyond the single representative spectrum stored in ``cube.qc``.
    """
    import pandas as pd

    values = _valid_values(cube, use_valid_only)
    n_valid_per_band = np.sum(np.isfinite(values), axis=0) if values.shape[0] else np.zeros(cube.n_bands)

    return pd.DataFrame(
        {
            "wavelength_nm": cube.wavelengths,
            "mean": mean_spectrum(cube, use_valid_only),
            "median": median_spectrum(cube, use_valid_only),
            "std": std_spectrum(cube, use_valid_only),
            "cv": coefficient_of_variation(cube, use_valid_only),
            "p10": percentile_spectrum(cube, 10, use_valid_only),
            "p90": percentile_spectrum(cube, 90, use_valid_only),
            "n_valid": n_valid_per_band.astype(int),
        }
    )
