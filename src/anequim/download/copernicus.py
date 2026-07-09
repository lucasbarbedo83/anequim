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

#: Where a CDSE refresh token is cached after an interactive login()
#: call, so subsequent calls (including from unattended scripts) don't
#: need your password or a fresh TOTP code — see login() and
#: _get_access_token_preferring_refresh().
CDSE_REFRESH_TOKEN_CACHE_PATH = os.path.expanduser("~/.anequim/cdse_refresh_token")

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


def get_access_token(totp: Optional[str] = None) -> str:
    """Obtain a short-lived CDSE OAuth2 access token from the
    ``CDSE_USERNAME``/``CDSE_PASSWORD`` environment variables.

    CDSE tokens expire quickly (on the order of minutes); this is called
    fresh for each :func:`fetch_olci_granules` invocation rather than
    cached across calls.

    Parameters
    ----------
    totp:
        Current 6-digit time-based one-time password, required if
        two-factor authentication is enabled on your CDSE account.
        Falls back to the ``CDSE_TOTP`` environment variable if not
        given explicitly (note a TOTP code is only valid for ~30
        seconds, so hardcoding one in an env var only works for a
        single immediate call, not for scripts run later).

    Raises
    ------
    DownloadNotAvailableError
        If authentication fails, with CDSE's own error description
        included (not just a generic HTTP error) — the most common
        causes are: (1) the account was created via SSO/institutional
        login (Google, EduGAIN, ...) rather than directly with an
        email+password on dataspace.copernicus.eu, which this
        password-grant flow cannot authenticate; (2) two-factor
        authentication is enabled and no/an incorrect ``totp`` was
        given; (3) an incorrect username or password.
    """
    requests = _require_requests()
    username, password = _get_credentials()
    data = {
        "client_id": CDSE_PUBLIC_CLIENT_ID,
        "username": username,
        "password": password,
        "grant_type": "password",
    }
    totp = totp or os.environ.get("CDSE_TOTP")
    if totp:
        data["totp"] = totp

    response = requests.post(CDSE_TOKEN_URL, data=data, timeout=30)
    if response.status_code != 200:
        try:
            detail = response.json()
            message = detail.get("error_description") or detail.get("error") or response.text
        except Exception:
            message = response.text
        raise DownloadNotAvailableError(
            f"CDSE authentication failed (HTTP {response.status_code}): {message}\n"
            "Common causes: (1) this account uses SSO/institutional login rather than a "
            "direct email+password CDSE account — the password-grant flow used here can't "
            "authenticate SSO accounts; (2) two-factor authentication is enabled on the "
            "account and a current TOTP code is required (pass totp=... to get_access_token, "
            "or set the CDSE_TOTP environment variable); (3) an incorrect username/password."
        )
    return response.json()["access_token"]


def login(totp: Optional[str] = None, persist: bool = True) -> str:
    """Authenticate interactively once and cache a refresh token, so
    later calls (including from unattended scripts) don't need your
    password or a fresh 2FA code — see module docstring.

    This is the recommended way to set up CDSE access when 2FA is
    enabled: call it once per session (passing your current TOTP code
    if 2FA is on), and :func:`fetch_olci_granules` will silently use the
    cached refresh token afterward, for as long as it remains valid.

    Parameters
    ----------
    totp:
        Current 6-digit 2FA code, if two-factor authentication is
        enabled on your account.
    persist:
        If True (default), save the refresh token to
        ``CDSE_REFRESH_TOKEN_CACHE_PATH`` (``~/.anequim/cdse_refresh_token``,
        created with owner-only permissions) for reuse by future Python
        processes, not just the current one.

    Returns
    -------
    The access token from this login (also usable immediately).
    """
    requests = _require_requests()
    username, password = _get_credentials()
    data = {
        "client_id": CDSE_PUBLIC_CLIENT_ID,
        "username": username,
        "password": password,
        "grant_type": "password",
    }
    totp = totp or os.environ.get("CDSE_TOTP")
    if totp:
        data["totp"] = totp

    response = requests.post(CDSE_TOKEN_URL, data=data, timeout=30)
    if response.status_code != 200:
        try:
            detail = response.json()
            message = detail.get("error_description") or detail.get("error") or response.text
        except Exception:
            message = response.text
        raise DownloadNotAvailableError(f"CDSE login failed (HTTP {response.status_code}): {message}")

    payload = response.json()
    refresh_token = payload.get("refresh_token")
    if persist and refresh_token:
        os.makedirs(os.path.dirname(CDSE_REFRESH_TOKEN_CACHE_PATH), exist_ok=True)
        with open(CDSE_REFRESH_TOKEN_CACHE_PATH, "w") as fh:
            fh.write(refresh_token)
        os.chmod(CDSE_REFRESH_TOKEN_CACHE_PATH, 0o600)
    return payload["access_token"]


def _refresh_access_token(refresh_token: str) -> Optional[dict]:
    """Exchange a refresh token for a new access token (and rotated
    refresh token), without needing username/password/TOTP. Returns
    ``None`` (rather than raising) if the refresh token has expired or
    is otherwise no longer valid, so callers can fall back cleanly.
    """
    requests = _require_requests()
    response = requests.post(
        CDSE_TOKEN_URL,
        data={
            "client_id": CDSE_PUBLIC_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if response.status_code != 200:
        return None
    return response.json()


def _get_access_token_preferring_refresh(totp: Optional[str] = None) -> str:
    """Token-acquisition strategy used internally by
    :func:`fetch_olci_granules`: try a cached refresh token first (no
    password or TOTP needed), and only fall back to a fresh
    username/password(+TOTP) login if no cached refresh token exists or
    it has expired.
    """
    cached_refresh_token = os.environ.get("CDSE_REFRESH_TOKEN")
    if not cached_refresh_token and os.path.isfile(CDSE_REFRESH_TOKEN_CACHE_PATH):
        with open(CDSE_REFRESH_TOKEN_CACHE_PATH) as fh:
            cached_refresh_token = fh.read().strip()

    if cached_refresh_token:
        payload = _refresh_access_token(cached_refresh_token)
        if payload is not None:
            new_refresh_token = payload.get("refresh_token")
            if new_refresh_token and os.path.isfile(CDSE_REFRESH_TOKEN_CACHE_PATH):
                with open(CDSE_REFRESH_TOKEN_CACHE_PATH, "w") as fh:
                    fh.write(new_refresh_token)
            return payload["access_token"]
        # Cached refresh token expired/invalid — fall through to a
        # fresh login below rather than raising.

    return login(totp=totp, persist=True)


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
    totp: Optional[str] = None,
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
    totp:
        Current 6-digit 2FA code, if two-factor authentication is
        enabled on your CDSE account — see :func:`get_access_token`.
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
    token = _get_access_token_preferring_refresh(totp=totp)

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
