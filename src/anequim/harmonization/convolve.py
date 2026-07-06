"""Spectral response function (SRF) convolution — opt-in harmonization,
planned.

Where :mod:`anequim.harmonization.interpolate` would do simple pointwise
resampling, this module is intended for the more rigorous case: given a
hyperspectral cube (e.g. PACE OCI) and a target sensor's per-band SRFs
(e.g. MODIS), convolve the hyperspectral spectrum with each target band's
SRF to simulate what that sensor would have measured — the standard
approach for rigorous cross-sensor consistency studies, as opposed to
naive linear interpolation.

Planned design
--------------
``convolve_to_srf(cube, srf_wavelengths, srf_weights)`` would, per target
band, compute a weighted integral of the native hyperspectral spectrum
against the (wavelength, weight) response curve, normalizing by the
integral of the response curve itself.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from ..core.exceptions import HarmonizationNotAvailableError
from ..core.spectral_cube import SpectralCube


def convolve_to_srf(
    cube: SpectralCube, band_srfs: Sequence[Tuple[Sequence[float], Sequence[float]]]
) -> SpectralCube:
    """Not yet implemented. See module docstring for the planned design.

    Parameters (planned)
    ---------------------
    band_srfs:
        One ``(wavelengths, weights)`` pair per target band.

    Raises
    ------
    HarmonizationNotAvailableError
        Always, in this release.
    """
    raise HarmonizationNotAvailableError(
        "anequim.harmonization.convolve_to_srf is not yet implemented."
    )
