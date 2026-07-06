"""Copernicus Marine Toolbox download support — planned, not yet
implemented.

Blocked on an OLCI reader existing (see
:mod:`anequim.readers.olci`); there is no point downloading files
anequim cannot yet parse. Once that reader lands, this module would
wrap the ``copernicusmarine`` package's subset/get APIs for Sentinel-3
OLCI WFR products, following the same
``fetch_olci_granules(longitude, latitude, target_time, ...)`` shape as
:func:`anequim.download.earthdata.fetch_pace_oci_granules` so
:func:`anequim.download.fetch_granules` can dispatch to either
transparently.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.config import TimeLike
from ..core.exceptions import DownloadNotAvailableError


def fetch_olci_granules(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    time_window_hours: float = 3.0,
    cache_dir: Optional[str] = None,
) -> List[str]:
    """Not yet implemented. See module docstring for the planned design.

    Raises
    ------
    DownloadNotAvailableError
        Always, in this release.
    """
    raise DownloadNotAvailableError(
        "Sentinel-3 OLCI download is not yet implemented (it is blocked on an OLCI "
        "reader, which is also not yet implemented — see anequim.readers.olci). "
        "Download OLCI granules yourself via the Copernicus Marine Toolbox for now."
    )
