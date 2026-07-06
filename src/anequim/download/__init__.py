"""Granule discovery/download — planned, not yet implemented.

Anequim v0.1 reads local files only, by design choice for this release
(see README). This module exists so the intended public API
(``anequim.download.fetch_granules(...)``) is stable to code against
ahead of time.

Planned design
--------------
- Wrap ``earthaccess`` for NASA OB.DAAC holdings (PACE, MODIS, VIIRS):
  search by short_name/collection, bounding box, and time range, then
  download matching granules to a local cache directory.
- Wrap the Copernicus Marine Toolbox (``copernicusmarine``) for
  Sentinel-3 OLCI products.
- A common ``fetch_granules(sensor, longitude, latitude, target_time,
  time_window_hours, cache_dir)`` function that returns local file paths
  ready to be handed to :func:`anequim.core.anequim.Anequim.get_rrs` via
  its ``files=`` argument — keeping the network/credentials concern
  fully separate from the retrieval and QC logic.
- Both integrations require the user's own credentials (NASA Earthdata
  login / Copernicus Marine account) and network access, neither of
  which this module will assume are available.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.config import TimeLike
from ..core.exceptions import DownloadNotAvailableError


def fetch_granules(
    sensor: str,
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    time_window_hours: float = 3.0,
    cache_dir: Optional[str] = None,
) -> List[str]:
    """Not yet implemented. Intended to search and download granules
    covering (longitude, latitude, target_time +/- time_window_hours)
    for the given sensor, returning local file paths.

    Raises
    ------
    DownloadNotAvailableError
        Always, in this release. Use your own download workflow (e.g.
        ``earthaccess`` or the Copernicus Marine Toolbox) to obtain
        granules, then pass their paths to
        ``Anequim.get_rrs(..., files=[...])``.
    """
    raise DownloadNotAvailableError(
        "anequim.download is not yet implemented in this release. Download granules "
        "yourself (e.g. via earthaccess for NASA OB.DAAC, or the Copernicus Marine "
        "Toolbox for Sentinel-3 OLCI) and pass local file paths to Anequim.get_rrs()."
    )
