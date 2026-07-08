"""NASA Earthdata / OB.DAAC granule search and download, via ``earthaccess``.

This is the first *implemented* half of :mod:`anequim.download` — it
covers PACE OCI (the sensor anequim has read end-to-end the longest).
Sentinel-3 OLCI download is also implemented, via the Copernicus Data
Space Ecosystem instead — see :mod:`anequim.download.copernicus`.

Requires the optional ``earthaccess`` dependency
(``pip install anequim[download]``) and a NASA Earthdata Login account
(free, at https://urs.earthdata.nasa.gov/). Authenticate once per
environment — either interactively (:func:`login`) or non-interactively
via a ``~/.netrc`` file — before calling
:func:`fetch_pace_oci_granules`.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import List, Optional

from ..core.config import TimeLike, parse_time
from ..core.exceptions import DownloadNotAvailableError

#: Default local cache directory for downloaded granules.
DEFAULT_CACHE_DIR = os.path.expanduser("~/.anequim/cache")

#: NASA CMR short names for the PACE OCI Level-2 AOP (Rrs) collection —
#: standard (science-quality, reprocessed) and near-real-time (NRT).
PACE_OCI_AOP_SHORT_NAME = "PACE_OCI_L2_AOP"
PACE_OCI_AOP_NRT_SHORT_NAME = "PACE_OCI_L2_AOP_NRT"


def _require_earthaccess():
    try:
        import earthaccess
    except ImportError as exc:  # pragma: no cover - exercised only without earthaccess
        raise DownloadNotAvailableError(
            "earthaccess is required for anequim.download.earthdata. Install it with "
            "`pip install anequim[download]` (or `pip install earthaccess` directly), "
            "then authenticate with a free NASA Earthdata Login account "
            "(https://urs.earthdata.nasa.gov/) — see anequim.download.earthdata.login()."
        ) from exc
    return earthaccess


def login(strategy: str = "netrc", persist: bool = False):
    """Authenticate with NASA Earthdata Login.

    Parameters
    ----------
    strategy:
        - "netrc": read credentials from ``~/.netrc`` (recommended for
          scripted/non-interactive use; see earthaccess docs for the
          expected file format).
        - "interactive": prompt for username/password in the current
          session.
        - "environment": read ``EARTHDATA_USERNAME`` / ``EARTHDATA_PASSWORD``
          environment variables.
    persist:
        If True (only meaningful with ``strategy="interactive"``), save
        the entered credentials to ``~/.netrc`` so future calls can use
        ``strategy="netrc"`` without prompting again.

    Returns
    -------
    The underlying ``earthaccess`` auth object (truthy if login succeeded).
    """
    earthaccess = _require_earthaccess()
    return earthaccess.login(strategy=strategy, persist=persist)


def fetch_pace_oci_granules(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    time_window_hours: float = 3.0,
    cache_dir: Optional[str] = None,
    near_real_time: bool = False,
    padding_deg: float = 0.5,
    count: int = 10,
) -> List[str]:
    """Search NASA CMR for PACE OCI L2 AOP granules covering (longitude,
    latitude) within ``+/- time_window_hours`` of ``target_time``, and
    download any matches to a local cache directory.

    Requires prior authentication (see :func:`login`) — a valid
    ``~/.netrc`` with Earthdata Login credentials is the simplest path
    for repeated/non-interactive use.

    Parameters
    ----------
    longitude, latitude:
        Target point, decimal degrees.
    target_time:
        Target time (ISO-8601 string or ``datetime``).
    time_window_hours:
        Half-width of the temporal search window, hours.
    cache_dir:
        Local directory to download into. Defaults to
        ``~/.anequim/cache``; created if it doesn't exist.
    near_real_time:
        If True, search the NRT (near-real-time) collection instead of
        the standard, reprocessed collection. NRT is available sooner
        after acquisition but is lower processing maturity.
    padding_deg:
        Half-width, in decimal degrees, of the bounding box used for the
        CMR spatial search around (longitude, latitude). CMR granule
        search works on bounding boxes, not points, so this must be wide
        enough that a granule's swath footprint (which may be offset
        from its nominal center) is still caught — 0.5 deg (~55 km) is a
        conservative default; narrow it for faster searches if you know
        your target sits well within a swath.
    count:
        Maximum number of granules to return from the search.

    Returns
    -------
    List of local file paths, ready to hand to
    ``Anequim(files=paths, sensor="OCI")``.  Returns an empty list (not
    an error) if the search found no matching granules — callers should
    check for this and raise/handle it in application-appropriate terms
    (:meth:`anequim.core.anequim.Anequim.retrieve_online` does this).
    """
    earthaccess = _require_earthaccess()

    target = parse_time(target_time)
    half = _dt.timedelta(hours=time_window_hours)
    temporal = (
        (target - half).strftime("%Y-%m-%dT%H:%M:%SZ"),
        (target + half).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    bounding_box = (
        longitude - padding_deg,
        latitude - padding_deg,
        longitude + padding_deg,
        latitude + padding_deg,
    )
    short_name = PACE_OCI_AOP_NRT_SHORT_NAME if near_real_time else PACE_OCI_AOP_SHORT_NAME

    results = earthaccess.search_data(
        short_name=short_name,
        temporal=temporal,
        bounding_box=bounding_box,
        count=count,
    )
    if not results:
        return []

    directory = cache_dir or DEFAULT_CACHE_DIR
    os.makedirs(directory, exist_ok=True)
    downloaded = earthaccess.download(results, directory)
    return [str(p) for p in downloaded]
