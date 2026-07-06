"""Generalized IOP algorithm (GIOP) — planned, not yet implemented.

GIOP (Werdell et al., 2013) is a flexible semi-analytical framework used
operationally by NASA OB.DAAC that fits Rrs with a linear-mixture IOP
model and configurable spectral basis functions (phytoplankton
absorption, CDOM+detrital absorption, particulate backscattering),
solved via nonlinear least squares.
"""

from __future__ import annotations

from ..core.exceptions import AlgorithmNotAvailableError
from ..core.spectral_cube import SpectralCube
from .base import BioOpticalAlgorithm


class GIOP(BioOpticalAlgorithm):
    name = "GIOP"

    def invert(self, cube: SpectralCube) -> dict:
        raise AlgorithmNotAvailableError(
            "GIOP is planned but not yet implemented in anequim.algorithms."
        )
