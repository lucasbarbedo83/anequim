"""Common interface planned for semi-analytical bio-optical inversion
algorithms (QAA, GIOP, GSM, ...).

Kept as a separate, optional module group (principle: "these remain
optional modules to keep the core package focused") so that Anequim's
core dependency footprint (numpy, netCDF4, pandas) never grows just
because an inversion algorithm needs, say, scipy optimization routines.
"""

from __future__ import annotations

import abc

from ..core.spectral_cube import SpectralCube


class BioOpticalAlgorithm(abc.ABC):
    """Planned common interface: every inversion algorithm consumes a
    :class:`~anequim.core.spectral_cube.SpectralCube` and returns a dict
    of derived per-pixel or representative-spectrum products (e.g.
    absorption/backscattering coefficients, chlorophyll-a).
    """

    name: str = "unknown"

    @abc.abstractmethod
    def invert(self, cube: SpectralCube) -> dict:
        """Run the inversion and return a dict of derived products."""
        raise NotImplementedError
