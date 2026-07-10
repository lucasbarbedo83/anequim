"""Granule discovery/download.

NASA Earthdata / OB.DAAC (PACE OCI, MODIS, VIIRS) is implemented via
``earthaccess`` — see :mod:`anequim.download.earthdata`. Sentinel-3
OLCI has two independent, interchangeable backends for the same
underlying data:

- :mod:`anequim.download.eumetsat` — EUMETSAT Data Store via the
  official ``eumdac`` client. **Default**, since it uses a static API
  key pair (no 2FA interaction).
- :mod:`anequim.download.copernicus` — Copernicus Data Space Ecosystem
  (CDSE) via its OData API. Alternative backend; useful if you already
  have a CDSE account, though note CDSE accounts with 2FA enabled need
  the extra ``totp=``/refresh-token setup documented in that module.

:func:`fetch_granules` is the single entry point that dispatches to the
right backend by sensor name (and, for OLCI, ``backend=`` choice),
keeping the network/credentials concern fully separate from retrieval
and QC logic. Its return value (a list of local file paths) is exactly
what :class:`anequim.core.anequim.Anequim` expects for its ``files=``
argument — and exactly what
:meth:`anequim.core.anequim.Anequim.retrieve_online` uses internally, so
the same one-call ``Anequim.retrieve_online(longitude, latitude, time,
sensor=...)`` interface works across sensors and agencies.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.config import TimeLike
from ..core.exceptions import DownloadNotAvailableError
from .earthdata import (
    login as earthdata_login,
    fetch_pace_oci_granules,
    fetch_modis_granules,
    fetch_viirs_granules,
)
from .copernicus import login as cdse_login, fetch_olci_granules as fetch_olci_granules_cdse
from .eumetsat import fetch_olci_granules as fetch_olci_granules_eumdac

_PACE_OCI_ALIASES = {"oci", "pace", "pace-oci", "pace_oci"}
_OLCI_ALIASES = {"olci", "sentinel3-olci", "sentinel-3"}
_MODIS_ALIASES = {"modis", "modis-aqua", "modis-terra"}
_VIIRS_ALIASES = {"viirs", "viirs-snpp", "viirs-noaa20"}

#: Backward-compatible default: `anequim.download.login` refers to the
#: NASA Earthdata login (the first backend implemented). For CDSE,
#: import `anequim.download.copernicus.login` (or `cdse_login`)
#: directly — the two services have unrelated credentials.
login = earthdata_login


def fetch_olci_granules(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    time_window_hours: float = 3.0,
    cache_dir: Optional[str] = None,
    backend: str = "eumdac",
    **kwargs,
) -> List[str]:
    """Search and download Sentinel-3 OLCI L2 WFR granules, via either
    the ``"eumdac"`` (EUMETSAT Data Store, default) or ``"cdse"``
    (Copernicus Data Space Ecosystem) backend — see module docstring.
    """
    if backend == "eumdac":
        return fetch_olci_granules_eumdac(
            longitude, latitude, target_time, time_window_hours, cache_dir, **kwargs
        )
    if backend == "cdse":
        return fetch_olci_granules_cdse(
            longitude, latitude, target_time, time_window_hours, cache_dir, **kwargs
        )
    raise ValueError(f"backend must be 'eumdac' or 'cdse', got {backend!r}")


def fetch_granules(
    sensor: str,
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    time_window_hours: float = 3.0,
    cache_dir: Optional[str] = None,
    **kwargs,
) -> List[str]:
    """Search and download granules for ``sensor`` covering (longitude,
    latitude) within ``+/- time_window_hours`` of ``target_time``.

    Dispatches to
    :func:`anequim.download.earthdata.fetch_pace_oci_granules` for
    ``sensor="OCI"`` (NASA Earthdata) or :func:`fetch_olci_granules` for
    ``sensor="OLCI"`` (EUMETSAT Data Store by default; pass
    ``backend="cdse"`` for Copernicus Data Space Ecosystem instead).
    Additional ``**kwargs`` are passed through to the matched backend.

    Raises
    ------
    DownloadNotAvailableError
        For any sensor other than PACE OCI or Sentinel-3 OLCI, since no
        other download backend is implemented yet.
    """
    key = sensor.strip().lower()
    if key in _PACE_OCI_ALIASES:
        return fetch_pace_oci_granules(
            longitude, latitude, target_time, time_window_hours, cache_dir, **kwargs
        )
    if key in _OLCI_ALIASES:
        return fetch_olci_granules(
            longitude, latitude, target_time, time_window_hours, cache_dir, **kwargs
        )
    if key in _MODIS_ALIASES:
        platform = kwargs.pop("platform", "Terra" if key == "modis-terra" else "Aqua")
        return fetch_modis_granules(
            longitude, latitude, target_time, time_window_hours, cache_dir, platform=platform, **kwargs
        )
    if key in _VIIRS_ALIASES:
        platform = kwargs.pop("platform", "NOAA-20" if key == "viirs-noaa20" else "SNPP")
        return fetch_viirs_granules(
            longitude, latitude, target_time, time_window_hours, cache_dir, platform=platform, **kwargs
        )
    raise DownloadNotAvailableError(
        f"Download is not yet implemented for sensor '{sensor}'. PACE OCI ('OCI'), "
        "Sentinel-3 OLCI ('OLCI'), MODIS ('MODIS'), and VIIRS ('VIIRS') are supported "
        "today; download other sensors' granules yourself for now and pass local file "
        "paths to Anequim.get_rrs()."
    )


__all__ = [
    "login",
    "earthdata_login",
    "cdse_login",
    "fetch_pace_oci_granules",
    "fetch_modis_granules",
    "fetch_viirs_granules",
    "fetch_olci_granules",
    "fetch_olci_granules_eumdac",
    "fetch_olci_granules_cdse",
    "fetch_granules",
]
