"""Wavelength interpolation — opt-in spectral harmonization, planned.

Per Anequim's design principle 2 ("preserve native spectral bands"),
nothing in the core retrieval path ever interpolates or resamples a
sensor's native Rrs bands. This module is where that behavior will live
*only* when a user explicitly asks for it (e.g. to compare PACE OCI's
hyperspectral bands against MODIS's fixed multispectral bands on a
common wavelength grid).

Planned design
--------------
``interpolate_to_wavelengths(cube, target_wavelengths, method="linear")``
would linearly (or, optionally, spline-) interpolate
``cube.qc.spectrum`` (and, if requested, the full ``cube.rrs`` pixel
cube) from its native ``cube.wavelengths`` onto ``target_wavelengths``
using ``numpy.interp``/``scipy.interpolate``, returning a *new*
SpectralCube-like object rather than mutating the original, and
recording the interpolation in its provenance ``extra`` field so it is
always traceable back to the native-resolution source.
"""

from __future__ import annotations

from typing import Iterable

from ..core.exceptions import HarmonizationNotAvailableError
from ..core.spectral_cube import SpectralCube


def interpolate_to_wavelengths(
    cube: SpectralCube, target_wavelengths: Iterable[float], method: str = "linear"
) -> SpectralCube:
    """Not yet implemented. See module docstring for the planned design.

    Raises
    ------
    HarmonizationNotAvailableError
        Always, in this release.
    """
    raise HarmonizationNotAvailableError(
        "anequim.harmonization.interpolate_to_wavelengths is not yet implemented. "
        "Work with each sensor's native cube.wavelengths for now."
    )
