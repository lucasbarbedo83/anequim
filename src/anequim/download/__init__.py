"""Granule discovery/download.

NASA Earthdata / OB.DAAC (PACE OCI) is implemented via ``earthaccess``
— see :mod:`anequim.download.earthdata`. Copernicus Data Space Ecosystem
(Sentinel-3 OLCI) is implemented via CDSE's OData API — see
:mod:`anequim.download.copernicus`.

:func:`fetch_granules` is the single entry point that dispatches to the
right backend by sensor name, keeping the network/credentials concern
fully separate from retrieval and QC logic. Its return value (a list of
local file paths) is exactly what :class:`anequim.core.anequim.Anequim`
expects for its ``files=`` argument — and exactly what
:meth:`anequim.core.anequim.Anequim.retrieve_online` uses internally, so
the same one-call ``Anequim.retrieve_online(longitude, latitude, time,
sensor=...)`` interface works for both PACE OCI and Sentinel-3 OLCI.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.config import TimeLike
from ..core.exceptions import DownloadNotAvailableError
from .earthdata import login, fetch_pace_oci_granules
from .copernicus import fetch_olci_granules

_PACE_OCI_ALIASES = {"oci", "pace", "pace-oci", "pace_oci"}
_OLCI_ALIASES = {"olci", "sentinel3-olci", "sentinel-3"}


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
    ``sensor="OCI"`` (NASA Earthdata) or
    :func:`anequim.download.copernicus.fetch_olci_granules` for
    ``sensor="OLCI"`` (Copernicus Data Space Ecosystem). Additional
    ``**kwargs`` are passed through to the matched backend (e.g.
    ``near_real_time=True`` for OCI; ``product_type=`` for OLCI;
    ``padding_deg=``/``count=`` for either).

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
    raise DownloadNotAvailableError(
        f"Download is not yet implemented for sensor '{sensor}'. PACE OCI ('OCI') and "
        "Sentinel-3 OLCI ('OLCI') are supported today; download other sensors' granules "
        "yourself for now and pass local file paths to Anequim.get_rrs()."
    )


__all__ = ["login", "fetch_pace_oci_granules", "fetch_olci_granules", "fetch_granules"]
