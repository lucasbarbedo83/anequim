"""Quasi-Analytical Algorithm (QAA) — planned, not yet implemented.

QAA (Lee et al., 2002 and later updates) semi-analytically inverts Rrs
to total absorption and backscattering coefficients using a sequence of
closed-form steps anchored at a reference wavelength, rather than a full
nonlinear optimization. It is one of the most widely used ocean-color
inversion schemes and a natural first candidate to implement here.
"""

from __future__ import annotations

from ..core.exceptions import AlgorithmNotAvailableError
from ..core.spectral_cube import SpectralCube
from .base import BioOpticalAlgorithm


class QAA(BioOpticalAlgorithm):
    name = "QAA"

    def invert(self, cube: SpectralCube) -> dict:
        raise AlgorithmNotAvailableError(
            "QAA is planned but not yet implemented in anequim.algorithms."
        )
