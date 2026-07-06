"""Sentinel-3 OLCI reader — planned, not yet implemented.

Design notes for a future implementation: Copernicus OLCI Level-2 WFR
(water full resolution) products are distributed as a directory of
per-band NetCDF files (e.g. ``Oa01_reflectance.nc`` ... ``Oa21_reflectance.nc``,
plus ``tie_geometries.nc``, ``geo_coordinates.nc``, ``wqsf.nc`` for
quality flags) rather than PACE/MODIS-style single-file granules with
internal groups. A real ``OlciL2Reader`` would need to accept a
*directory* path, open the relevant per-band files together, and stack
them into the same (rows, cols, bands) Rrs cube contract used by
:class:`~anequim.readers.base.SensorReader`, converting OLCI's
top-of-atmosphere-corrected water-leaving reflectance to Rrs (dividing
by pi) to keep units consistent across sensors.
"""

from __future__ import annotations

from ._stub import _StubReader


class OlciL2Reader(_StubReader):
    sensor_name = "Sentinel3-OLCI"

    @classmethod
    def matches(cls, path: str) -> bool:
        # Real implementation would detect an OLCI product directory
        # (e.g. presence of geo_coordinates.nc + Oa*_reflectance.nc) or
        # a manifest.xml with an OLCI product type. Left conservative
        # (always False) so it never falsely claims a granule today.
        return False
