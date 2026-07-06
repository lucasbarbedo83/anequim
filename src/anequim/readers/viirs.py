"""VIIRS (SNPP/NOAA-20/NOAA-21) ocean color reader — planned, not yet
implemented.

Design notes: NASA OB.DAAC VIIRS Level-2 ``OC`` granules follow the same
general single-file, grouped-NetCDF layout as MODIS and PACE OCI
(``navigation_data``, ``geophysical_data/Rrs`` with a fixed multispectral
``wavelength`` dimension rather than OCI's hyperspectral one,
``geophysical_data/l2_flags``, ``scan_line_attributes``). A real
``ViirsL2Reader`` would likely share the bulk of its implementation with
a future MODIS reader through a common "classic OBPG multispectral L2"
base class, since the file conventions are nearly identical between the
two missions.
"""

from __future__ import annotations

from ._stub import _StubReader


class ViirsL2Reader(_StubReader):
    sensor_name = "VIIRS"

    @classmethod
    def matches(cls, path: str) -> bool:
        # Real implementation: open the file and check global attributes
        # 'instrument' == 'VIIRS' and 'platform' in {'SNPP', 'NOAA-20', 'NOAA-21'}.
        return False
