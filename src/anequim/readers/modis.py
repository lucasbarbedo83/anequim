"""Reader for MODIS-Aqua / MODIS-Terra Level-2 OC granules.

Thin subclass of :class:`~anequim.readers._obpg_multiband.ObpgMultibandL2Reader`
— MODIS L2 OC files follow the classic OBPG multiband layout (see that
module's docstring for the confirmed file-format details), storing Rrs
as separate ``Rrs_412``, ``Rrs_443``, ... variables rather than a single
hyperspectral array. Standard MODIS-Aqua/Terra Rrs bands are 412, 443,
469, 488, 531, 547, 555, 645, 667, and 678 nm, discovered directly from
each file rather than hardcoded.
"""

from __future__ import annotations

from ._obpg_multiband import ObpgMultibandL2Reader


class ModisL2Reader(ObpgMultibandL2Reader):
    sensor_name = "MODIS"
    #: MODIS ocean color bands are nominally 1 km at nadir.
    nominal_pixel_size_m = 1000.0

    @classmethod
    def matches(cls, path: str) -> bool:
        import netCDF4

        try:
            with netCDF4.Dataset(path, mode="r") as ds:
                instrument = str(getattr(ds, "instrument", "")).upper()
                platform = str(getattr(ds, "platform", "")).upper()
                return "MODIS" in instrument and platform in ("AQUA", "TERRA")
        except Exception:
            return False
