"""
anequim.atmosphere
====================

Atmospheric radiative-transfer utilities: Frouin-algorithm hyperspectral
downwelling irradiance just above the sea surface, integrated with
:class:`anequim.core.spectral_cube.SpectralCube`.
"""

from .frouin_irradiance import (
    AtmosphericState,
    FrouinIrradiance,
    default_solar_spectrum,
    aod550_from_aot865,
    atmospheric_state_from_cube,
)

__all__ = [
    "AtmosphericState",
    "FrouinIrradiance",
    "default_solar_spectrum",
    "aod550_from_aot865",
    "atmospheric_state_from_cube",
]
