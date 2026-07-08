"""Sentinel-3 OLCI L2 WFR granule search and download, via the
**Copernicus Data Space Ecosystem (CDSE)** OData API.

Note on which Copernicus service this is: raw Level-2 SAFE-format
swath granules (what :class:`anequim.readers.olci.OlciL2Reader` parses)
are distributed by CDSE (`dataspace.copernicus.eu`), not by the
"Copernicus Marine Service"/"Copernicus Marine Toolbox"
(`marine.copernicus.eu`), which instead serves curated, gridded L3/L4
products. This module talks to CDSE directly via ``requests`` against
its documented OData endpoints, rather than assume a specific
third-party client library — CDSE's own Python tooling landscape is
fragmented and less standardized than NASA's ``earthaccess``.

Requires:
- The optional ``requests`` dependency (``pip install anequim[download]``).
- A free CDSE account (https://dataspace.copernicus.eu/) and its
  username/password set as the ``CDSE_USERNAME`` / ``CDSE_PASSWORD``
  environment variables (CDSE issues short-lived OAuth2 tokens from
  these credentials automatically — there is no separate "API key" to
  generate).
"""

from __future__ import annotations

import datetime as _dt
import os
import zipfile
from typing import List, Optional

from ..core.config import TimeLike, parse_time
from ..core.exceptions import DownloadNotAvailableError

DEFAULT_CACHE_DIR = os.path.expanduser("~/.anequim/cache/olci")

CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)
CDSE_ODATA_PRODUCTS_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
CDSE_PUBLIC_CLIENT_ID = "cdse-public"

#: OLCI L2 WFR product type code as encoded in a CDSE product's Name.
DEFAULT_OLCI_PRODUCT_TYPE = "OL_2_WFR___"


def _require_requests():
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - exercised only without requests
        raise DownloadNotAvailableError(
            "the `requests` package is required for anequim.download.copernicus. Install it "
            "with `pip install anequim[download]` (or `pip install requests` directly)."
        ) from exc
    return requests


def _get_credentials() -> "tuple[str, str]":
    username = os.environ.get("CDSE_USERNAME")
    password = os.environ.get("CDSE_PASSWORD")
    if not username or not password:
        raise DownloadNotAvailableError(
            "CDSE credentials not found. Create a free Copernicus Data Space Ecosystem "
            "account (https://dataspace.copernicus.eu/) and set the CDSE_USERNAME and "
            "CDSE_PASSWORD environment variables."
        )
    return username, password


def get_access_token() -> str:
    """Obtain a short-lived CDSE OAuth2 access token from the
    ``CDSE_USERNAME``/``CDSE_PASSWORD`` environment variables.

    CDSE tokens expire quickly (on the order of minutes); this is called
    fresh for each :func:`fetch_olci_granules` invocation rather than
    cached across calls.
    """
    requests = _require_requests()
    username, password = _get_credentials()
    response = requests.post(
        CDSE_TOKEN_URL,
        data={
            "client_id": CDSE_PUBLIC_CLIENT_ID,
            "username": username,
            "password": password,
            "grant_type": "password",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _build_odata_filter(
    longitude: float,
    latitude: float,
    padding_deg: float,
    start_iso: str,
    end_iso: str,
    product_type: str,
) -> str:
    lon_min, lat_min = longitude - padding_deg, latitude - padding_deg
    lon_max, lat_max = longitude + padding_deg, latitude + padding_deg
    polygon = (
        f"POLYGON(({lon_min} {lat_min},{lon_max} {lat_min},{lon_max} {lat_max},"
        f"{lon_min} {lat_max},{lon_min} {lat_min}))"
    )
    return (
        f"Collection/Name eq 'SENTINEL-3' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {start_iso} and ContentDate/Start lt {end_iso} and "
        f"contains(Name,'{product_type}')"
    )


def _extract_safe_directory(zip_path: str, extract_root: str) -> str:
    """Extract a downloaded CDSE product zip and return the path to the
    ``.SEN3`` SAFE directory inside it (identified by containing an
    ``xfdumanifest.xml`` marker — the same marker
    :func:`anequim.utils.file_discovery.resolve_files` looks for)."""
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


def fetch_olci_granules(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    time_window_hours: float = 3.0,
    cache_dir: Optional[str] = None,
    product_type: str = DEFAULT_OLCI_PRODUCT_TYPE,
    padding_deg: float = 0.5,
    count: int = 10,
) -> List[str]:
    """Search CDSE for Sentinel-3 OLCI L2 WFR granules covering
    (longitude, latitude) within ``+/- time_window_hours`` of
    ``target_time``, download and unzip any matches, and return the
    local ``.SEN3`` SAFE directory paths.

    Requires ``CDSE_USERNAME``/``CDSE_PASSWORD`` environment variables
    (see module docstring). Returned paths are ready to hand to
    ``Anequim(files=paths, sensor="OLCI")``.

    Parameters
    ----------
    padding_deg:
        Half-width, in decimal degrees, of the bounding polygon used for
        the CDSE spatial search around (longitude, latitude). See the
        equivalent parameter in
        :func:`anequim.download.earthdata.fetch_pace_oci_granules` for
        the same rationale (swath footprints can be offset from a
        granule's nominal center).
    product_type:
        CDSE product-type code to match against each result's ``Name``.
        Defaults to full-resolution water products (``OL_2_WFR___``);
        pass ``"OL_2_WRR___"`` for reduced-resolution instead.

    Returns
    -------
    List of local ``.SEN3`` directory paths — empty (not an error) if no
    granules matched.
    """
    requests = _require_requests()

    target = parse_time(target_time)
    half = _dt.timedelta(hours=time_window_hours)
    start_iso = (target - half).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_iso = (target + half).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    odata_filter = _build_odata_filter(longitude, latitude, padding_deg, start_iso, end_iso, product_type)
    response = requests.get(
        CDSE_ODATA_PRODUCTS_URL,
        params={"$filter": odata_filter, "$top": count, "$orderby": "ContentDate/Start"},
        timeout=60,
    )
    response.raise_for_status()
    results = response.json().get("value", [])
    if not results:
        return []

    directory = cache_dir or DEFAULT_CACHE_DIR
    os.makedirs(directory, exist_ok=True)
    token = get_access_token()

    paths = []
    for product in results:
        product_id = product["Id"]
        product_name = product["Name"]
        extract_root = os.path.join(directory, product_id)

        existing = None
        if os.path.isdir(extract_root):
            for root, dirs, files in os.walk(extract_root):
                if "xfdumanifest.xml" in files:
                    existing = root
                    break

        if existing is not None:
            paths.append(existing)
            continue

        zip_path = os.path.join(directory, f"{product_name}.zip")
        download_url = f"{CDSE_ODATA_PRODUCTS_URL}({product_id})/$value"
        headers = {"Authorization": f"Bearer {token}"}
        with requests.get(download_url, headers=headers, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)

        safe_dir = _extract_safe_directory(zip_path, extract_root)
        os.remove(zip_path)
        paths.append(safe_dir)

    return paths
