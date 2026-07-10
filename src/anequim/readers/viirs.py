"""Reader for VIIRS (SNPP / NOAA-20 / NOAA-21) Level-2 OC granules.

Thin subclass of :class:`~anequim.readers._obpg_multiband.ObpgMultibandL2Reader`
— VIIRS L2 OC files follow the same classic OBPG multiband layout as
MODIS (per-band ``Rrs_<wavelength>`` variables). Standard VIIRS-SNPP
Rrs bands are M1-M5 (410, 443, 486, 551, 671 nm); NOAA-20/NOAA-21 center
wavelengths differ very slightly (e.g. 411, 445, 489, 556, 667 nm for
NOAA-20) — again, discovered directly from each file's own
``Rrs_<wavelength>`` variable names rather than hardcoded, so these
small cross-platform differences are handled automatically.
"""

from __future__ import annotations

from ._obpg_multiband import ObpgMultibandL2Reader

#: Global-attribute `platform` values seen across VIIRS L2 OC granules
#: for each mission (metadata conventions have varied over time — e.g.
#: SNPP granules have used both "NPP" and "Suomi-NPP").
_VIIRS_PLATFORMS = {"SNPP", "NPP", "SUOMI-NPP", "NOAA-20", "JPSS-1", "NOAA-21", "JPSS-2"}


class ViirsL2Reader(ObpgMultibandL2Reader):
    sensor_name = "VIIRS"
    #: VIIRS moderate-resolution (M-band) ocean color products are
    #: nominally 750 m at nadir (aggregated across most of the scan to
    #: control the bow-tie effect; larger toward the swath edge).
    nominal_pixel_size_m = 750.0

    @classmethod
    def matches(cls, path: str) -> bool:
        import netCDF4

        try:
            with netCDF4.Dataset(path, mode="r") as ds:
                instrument = str(getattr(ds, "instrument", "")).upper()
                platform = str(getattr(ds, "platform", "")).upper()
                return "VIIRS" in instrument and platform in _VIIRS_PLATFORMS
        except Exception:
            return False
