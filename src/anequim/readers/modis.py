"""MODIS-Aqua / MODIS-Terra ocean color reader — planned, not yet
implemented.

Design notes: NASA OB.DAAC MODIS Level-2 ``OC`` granules follow the same
grouped-NetCDF layout referenced in :mod:`anequim.readers.viirs`
(fixed multispectral bands: 412, 443, 469, 488, 531, 547, 555, 645, 667,
678 nm Rrs, plus the standard ``l2_flags``). A real ``ModisL2Reader``
would be implemented as a thin subclass of the same shared "classic OBPG
multispectral L2" base proposed for VIIRS.
"""

from __future__ import annotations

from ._stub import _StubReader


class ModisL2Reader(_StubReader):
    sensor_name = "MODIS"

    @classmethod
    def matches(cls, path: str) -> bool:
        # Real implementation: check global attributes 'instrument' ==
        # 'MODIS' and 'platform' in {'Aqua', 'Terra'}.
        return False
