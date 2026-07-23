"""Point atmospheric ancillary data (ozone, water vapor, surface
pressure) for a single (longitude, latitude, time), via NASA Earthdata,
using ``earthaccess`` — the same access layer as
:mod:`anequim.download.earthdata`.

This is deliberately kept separate from granule download: it returns
scalar physical quantities for one location/time, not local file paths
for a satellite scene. It exists to fill in the atmospheric state that
:class:`~anequim.core.anequim.Anequim.get_rrs` cannot get from the
granule itself — PACE OCI's ``OC_AOP`` product carries aerosol optical
depth, Angstrom exponent, and sun/view geometry (see
:mod:`anequim.readers.pace_oci`), but not total column ozone or
water vapor, which the Frouin surface-irradiance model
(:mod:`anequim.atmosphere.frouin_irradiance`) also needs.

Data sources
------------
Ozone (total column, Dobson Units):
    OMI/Aura Level-3 daily gridded ozone, short_name "OMTO3d"
    (1x1 degree, HDF-EOS5), served via NASA Earthdata / GES DISC.
    https://disc.gsfc.nasa.gov/datasets/OMTO3d_003

Water vapor + surface pressure:
    MERRA-2 hourly single-level diagnostics, short_name "M2T1NXSLV"
    (TQV = total precipitable water vapor [kg m^-2],
    PS = surface pressure [Pa]), also via NASA Earthdata / GES DISC.
    https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/

Both collections are read with ``netCDF4`` directly (already a core
anequim dependency — see :mod:`anequim.readers.pace_oci` for the same
pattern), not ``xarray``, to avoid adding a second NetCDF-reading
dependency to the project.

Requires the optional ``earthaccess`` dependency
(``pip install anequim[download]``) and NASA Earthdata Login
credentials — see :func:`anequim.download.earthdata.login`.

IMPORTANT — not exercised against live services
--------------------------------------------------
Written and structurally verified (config wiring, earthaccess-mocked
call shape, unit conversions) without network access to GES DISC. The
NetCDF group/variable names are the documented ones, but you should
sanity-check the first real granule you fetch:
``netCDF4.Dataset(path).groups`` / ``.variables`` (OMTO3d is
HDF-EOS5-nested; MERRA-2 is flat).
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import Dict, Optional

from ..core.config import TimeLike, parse_time
from ..core.exceptions import DownloadNotAvailableError
from .earthdata import _require_earthaccess, DEFAULT_CACHE_DIR as _EARTHDATA_CACHE_DIR

#: Local cache directory for downloaded ancillary files — kept separate
#: from the granule cache (anequim.download.earthdata.DEFAULT_CACHE_DIR)
#: since these are small, frequently-reused daily/hourly global files.
DEFAULT_CACHE_DIR = os.path.expanduser("~/.anequim/cache/ancillary")

OMTO3D_SHORT_NAME = "OMTO3d"
MERRA2_SLV_SHORT_NAME = "M2T1NXSLV"


def _search_and_download_one(short_name: str, temporal, cache_dir: Optional[str]) -> str:
    """Search for the single granule covering ``temporal`` and download
    it, returning its local path. Shared by the two fetchers below."""
    earthaccess = _require_earthaccess()
    results = earthaccess.search_data(short_name=short_name, temporal=temporal, count=1)
    if not results:
        raise DownloadNotAvailableError(
            f"No {short_name} granule found for {temporal[0]} .. {temporal[1]}"
        )
    directory = cache_dir or DEFAULT_CACHE_DIR
    os.makedirs(directory, exist_ok=True)
    downloaded = earthaccess.download(results[:1], directory)
    return str(downloaded[0])


def _daily_temporal_window(target_time: TimeLike) -> tuple:
    """(start, end) ISO strings spanning the whole UTC day of
    ``target_time`` — OMTO3d and M2T1NXSLV are daily/hourly products
    keyed by date, not by the exact match-up time."""
    target = parse_time(target_time)
    day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)
    return (
        day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        day_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def fetch_ozone_omi(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    cache_dir: Optional[str] = None,
) -> float:
    """Total column ozone (Dobson Units) at (longitude, latitude) for
    the UTC day of ``target_time``, from OMI/Aura OMTO3d.

    Raises
    ------
    DownloadNotAvailableError
        If ``earthaccess`` is not installed, or no granule is found —
        callers wanting a graceful degrade should catch this
        themselves (e.g. to fall back to a climatological value); this
        function does not silently substitute one, matching
        ``get_rrs``'s error-first convention (see
        ``OutsideSpatialDomainError`` / ``OutsideTimeWindowError``).
    """
    temporal = _daily_temporal_window(target_time)
    path = _search_and_download_one(OMTO3D_SHORT_NAME, temporal, cache_dir)

    import netCDF4

    with netCDF4.Dataset(path, mode="r") as ds:
        group = ds
        for part in ("HDFEOS", "GRIDS", "OMI Column Amount O3", "Data Fields"):
            group = group.groups[part]
        ozone_grid = group.variables["ColumnAmountO3"][:]

        # OMTO3d is a global 1x1 degree grid, cell centers at
        # (-179.5 .. 179.5, -89.5 .. 89.5).
        lon_idx = int(round(longitude + 179.5))
        lat_idx = int(round(latitude + 89.5))
        value = ozone_grid[lat_idx, lon_idx]

    import numpy as np

    if np.ma.is_masked(value):
        raise DownloadNotAvailableError(
            f"OMTO3d ozone is masked (likely polar-night gap) at ({longitude}, {latitude})"
        )
    return float(value)


def fetch_merra2_meteorology(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    cache_dir: Optional[str] = None,
) -> Dict[str, float]:
    """Total precipitable water vapor (cm) and surface pressure (hPa)
    at (longitude, latitude, target_time), from MERRA-2 M2T1NXSLV.

    Raises
    ------
    DownloadNotAvailableError
        See :func:`fetch_ozone_omi` — no silent fallback.
    """
    temporal = _daily_temporal_window(target_time)
    path = _search_and_download_one(MERRA2_SLV_SHORT_NAME, temporal, cache_dir)

    import netCDF4
    import numpy as np

    with netCDF4.Dataset(path, mode="r") as ds:
        lats = ds.variables["lat"][:]
        lons = ds.variables["lon"][:]
        times = netCDF4.num2date(ds.variables["time"][:], ds.variables["time"].units)

        target = parse_time(target_time).replace(tzinfo=None)
        t_idx = int(np.argmin([abs((t - target).total_seconds()) for t in times]))
        lat_idx = int(np.argmin(np.abs(lats - latitude)))
        lon_idx = int(np.argmin(np.abs(lons - longitude)))

        tqv_kg_m2 = float(ds.variables["TQV"][t_idx, lat_idx, lon_idx])
        ps_pa = float(ds.variables["PS"][t_idx, lat_idx, lon_idx])

    return {
        "water_vapor_cm": tqv_kg_m2 / 10.0,  # 1 kg/m^2 liquid water == 0.1 cm depth
        "surface_pressure_hpa": ps_pa / 100.0,
    }


def fetch_atmospheric_ancillary(
    longitude: float,
    latitude: float,
    target_time: TimeLike,
    cache_dir: Optional[str] = None,
) -> Dict[str, float]:
    """Fetch everything :mod:`anequim.atmosphere.frouin_irradiance`
    needs beyond what the granule itself provides: ``ozone_du`` (OMI/
    Aura) and ``water_vapor_cm`` / ``surface_pressure_hpa`` (MERRA-2).

    Aerosol optical depth is intentionally NOT fetched here — PACE
    OCI's own ``aot_865`` + ``angstrom`` (already in
    ``SpectralCube.atmospheric`` when ``include_atmospheric=True``)
    are scene-matched and higher resolution than MERRA-2's reanalysis
    aerosol field, so use those instead
    (:func:`anequim.atmosphere.frouin_irradiance.aod550_from_aot865`).

    This is the function wired into
    :meth:`anequim.core.anequim.Anequim.get_rrs` via
    ``include_ancillary_atmosphere=True``.
    """
    ozone_du = fetch_ozone_omi(longitude, latitude, target_time, cache_dir)
    meteo = fetch_merra2_meteorology(longitude, latitude, target_time, cache_dir)
    return {"ozone_du": ozone_du, **meteo}
