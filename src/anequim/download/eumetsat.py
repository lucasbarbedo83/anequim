"""Sentinel-3 OLCI L2 WFR granule search and download via **EUMETSAT's
Data Store**, using the official ``eumdac`` Python client.

This is an alternative backend to :mod:`anequim.download.copernicus`
(CDSE) for the same OLCI L2 WFR product — same underlying data, +
different agency portal, credentials, and client library. Confirmed
against EUMETSAT/WEkEO's official "learn-olci" training material
(gitlab.eumetsat.int/eumetlab/oceans/ocean-training/sensors/learn-olci)
and EUMDAC's own documentation and collection catalog
(api.eumetsat.int/data/browse/collections).

Requires:
- The optional ``eumdac`` package (``pip install anequim[download]``).
- A free EUMETSAT User Portal account
  (https://user.eumetsat.int/register).
- **Important, easy to miss**: after registering, log in to the User
  Portal, open your profile, go to "My data licenses", and enable
  "Meteosat > 1hr latency & Metop, Copernicus data & Third party data".
  Without this, Sentinel-3 products are not accessible even with valid
  credentials/tokens.
- A consumer key/secret from https://api.eumetsat.int/api-key, set as
  the ``EUMETSAT_CONSUMER_KEY`` / ``EUMETSAT_CONSUMER_SECRET``
  environment variables. Unlike CDSE, this credential type has no 2FA
  interaction — it's a static API key pair, generated once from the
  portal.
"""

from __future__ import annotations

import datetime as _dt
import os
import shutil
import zipfile
from typing import List, Optional

from ..core.config import TimeLike, parse_time
from ..core.exceptions import DownloadNotAvailableError

DEFAULT_CACHE_DIR = os.path.expanduser("~/.anequim/cache/olci")

#: Operational (continuously updated with current data) OLCI L2
#: full-resolution ocean colour collection.
OLCI_L2_WFR_OPERATIONAL_COLLECTION = "EO:EUM:DAT:0407"
#: Reprocessed (more consistent processing baseline, historical
#: archive — check EUMETSAT's release notes for its current end date)
#: collection for the same product.
OLCI_L2_WFR_REPROCESSED_COLLECTION = "EO:EUM:DAT:0556"


def _require_eumdac():
    try:
        import eumdac
    except ImportError as exc:  # pragma: no cover - exercised only without eumdac
        raise DownloadNotAvailableError(
            "the `eumdac` package is required for anequim.download.eumetsat. Install it "
            "with `pip install anequim[download]` (or `pip install eumdac` directly)."
        ) from exc
    return eumdac


def _get_credentials() -> "tuple[str, str]":
    key = os.environ.get("EUMETSAT_CONSUMER_KEY")
    secret = os.environ.get("EUMETSAT_CONSUMER_SECRET")
    if not key or not secret:
        raise DownloadNotAvailableError(
            "EUMETSAT credentials not found. Create a free EUMETSAT User Portal account "
            "(https://user.eumetsat.int/register), enable Sentinel-3/Copernicus data access "
            "under your profile's 'My data licenses' tab, generate a consumer key/secret at "
            "https://api.eumetsat.int/api-key, and set the EUMETSAT_CONSUMER_KEY / "
            "EUMETSAT_CONSUMER_SECRET environment variables."
        )
    return key, secret


def get_datastore():
    """Return an authenticated ``eumdac.DataStore`` instance, ready to
    search collections."""
    eumdac = _require_eumdac()
    key, secret = _get_credentials()
    token = eumdac.AccessToken((key, secret))
    return eumdac.DataStore(token)


def _extract_safe_directory(zip_path: str, extract_root: str) -> str:
    """Extract a downloaded product zip and return the path to the
    ``.SEN3`` SAFE directory inside it (identified by an
    ``xfdumanifest.xml`` marker)."""
    os.makedirs(extract_root, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_root)
    for root, dirs, files in os.walk(extract_root):
        if "xfdumanifest.xml" in files:
            return root
    raise DownloadNotAvailableError(
        f"Downloaded product at {zip_path} did not contain an xfdumanifest.xml "
        "SAFE marker after extraction; the product format may have changed."
    )


def _find_existing_safe_dir(extract_root: str) -> Optional[str]:
    if not os.path.isdir(extract_root):
        return None
    for root, dirs, files in os.walk(extract_root):
        if "xfdumanifest.xml" in files:
            return root
    return None


def fetch_olci_granules(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    time_window_hours: float = 3.0,
    cache_dir: Optional[str] = None,
    collection_id: str = OLCI_L2_WFR_OPERATIONAL_COLLECTION,
    padding_deg: float = 0.5,
    count: int = 10,
) -> List[str]:
    """Search EUMETSAT's Data Store for Sentinel-3 OLCI L2 WFR granules
    covering (longitude, latitude) within ``+/- time_window_hours`` of
    ``target_time``, download and unzip any matches, and return the
    local ``.SEN3`` SAFE directory paths.

    Requires ``EUMETSAT_CONSUMER_KEY``/``EUMETSAT_CONSUMER_SECRET``
    environment variables (see module docstring). Returned paths are
    ready to hand to ``Anequim(files=paths, sensor="OLCI")``.

    Parameters
    ----------
    collection_id:
        EUMETSAT Data Store collection to search. Defaults to the
        operational (continuously updated) collection
        (``EO:EUM:DAT:0407``); pass
        ``OLCI_L2_WFR_REPROCESSED_COLLECTION`` for the reprocessed
        archive instead, which may be more appropriate for older dates.
    padding_deg:
        Half-width, in decimal degrees, of the bounding polygon used for
        the spatial search around (longitude, latitude) — see the
        equivalent parameter in
        :func:`anequim.download.copernicus.fetch_olci_granules` for the
        same rationale.

    Returns
    -------
    List of local ``.SEN3`` directory paths — empty (not an error) if no
    granules matched.
    """
    eumdac = _require_eumdac()
    datastore = get_datastore()

    target = parse_time(target_time)
    half = _dt.timedelta(hours=time_window_hours)
    dtstart = (target - half).astimezone(_dt.timezone.utc).replace(tzinfo=None)
    dtend = (target + half).astimezone(_dt.timezone.utc).replace(tzinfo=None)

    lon_min, lat_min = longitude - padding_deg, latitude - padding_deg
    lon_max, lat_max = longitude + padding_deg, latitude + padding_deg
    polygon_wkt = (
        f"POLYGON(({lon_min} {lat_min},{lon_max} {lat_min},{lon_max} {lat_max},"
        f"{lon_min} {lat_max},{lon_min} {lat_min}))"
    )

    try:
        collection = datastore.get_collection(collection_id)
        search_results = list(
            collection.search(dtstart=dtstart, dtend=dtend, geo=polygon_wkt)
        )
    except Exception as exc:
        raise DownloadNotAvailableError(f"EUMETSAT Data Store search failed: {exc}") from exc

    if not search_results:
        return []
    search_results = search_results[:count]

    directory = cache_dir or DEFAULT_CACHE_DIR
    os.makedirs(directory, exist_ok=True)

    paths = []
    for product in search_results:
        product_name = str(product)
        extract_root = os.path.join(directory, product_name)

        existing = _find_existing_safe_dir(extract_root)
        if existing is not None:
            paths.append(existing)
            continue

        os.makedirs(extract_root, exist_ok=True)
        zip_path = os.path.join(extract_root, f"{product_name}.zip")
        with product.open() as fsrc, open(zip_path, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)

        safe_dir = _extract_safe_directory(zip_path, extract_root)
        os.remove(zip_path)
        paths.append(safe_dir)

    return paths
