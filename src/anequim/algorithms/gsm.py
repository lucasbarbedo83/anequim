"""Garver-Siegel-Maritorena algorithm (GSM) — planned, not yet implemented.

GSM (Maritorena, Siegel & Peterson, 2002) is a semi-analytical model
that simultaneously retrieves chlorophyll-a, CDOM+detrital absorption,
and particulate backscattering from Rrs via nonlinear optimization
against a fixed bio-optical model, historically used to produce some
NASA OC merged-sensor climate data records.
"""

from __future__ import annotations

from ..core.exceptions import AlgorithmNotAvailableError
from ..core.spectral_cube import SpectralCube
from .base import BioOpticalAlgorithm


class GSM(BioOpticalAlgorithm):
    name = "GSM"

    def invert(self, cube: SpectralCube) -> dict:
        raise AlgorithmNotAvailableError(
            "GSM is planned but not yet implemented in anequim.algorithms."
        )
