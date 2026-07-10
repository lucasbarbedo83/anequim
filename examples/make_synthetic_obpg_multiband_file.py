"""Generate a small, structurally-realistic synthetic classic-OBPG
multiband L2 granule (the MODIS/VIIRS file format: per-band
``Rrs_<wavelength>`` variables) for testing/demos, without network
access to a real NASA OB.DAAC file.

Reuses the same phytoplankton-like spectral shape helper as the PACE
OCI synthetic generator, but writes it out in the different per-band
variable layout that
:class:`anequim.readers._obpg_multiband.ObpgMultibandL2Reader` expects.
"""

from __future__ import annotations

import datetime as _dt
import os

import numpy as np

from make_synthetic_pace_file import _rrs_spectrum_shape

#: Standard MODIS-Aqua Rrs bands (nm).
MODIS_AQUA_BANDS = (412, 443, 469, 488, 531, 547, 555, 645, 667, 678)
#: Standard VIIRS-SNPP Rrs bands (nm).
VIIRS_SNPP_BANDS = (410, 443, 486, 551, 671)


def make_synthetic_obpg_multiband_file(
    path: str,
    instrument: str = "MODIS",
    platform: str = "Aqua",
    bands=MODIS_AQUA_BANDS,
    center_lon: float = -70.5,
    center_lat: float = 41.3,
    n_lines: int = 20,
    n_pixels: int = 20,
    acquisition_time: "_dt.datetime | None" = None,
    cloud_fraction: float = 0.1,
    land_corner: bool = True,
    seed: int = 0,
) -> str:
    """Write a synthetic MODIS/VIIRS-shaped L2 OC NetCDF file to ``path``.

    Returns ``path`` for convenience.
    """
    import netCDF4

    rng = np.random.default_rng(seed)

    if acquisition_time is None:
        acquisition_time = _dt.datetime(2024, 6, 15, 14, 42, 0, tzinfo=_dt.timezone.utc)

    wavelengths = np.array(sorted(bands), dtype=float)
    n_bands = len(wavelengths)

    row_offsets = (np.arange(n_lines) - n_lines / 2) * 0.01
    col_offsets = (np.arange(n_pixels) - n_pixels / 2) * 0.01
    jitter = rng.normal(scale=0.01 * 0.02, size=(n_lines, n_pixels))
    lat_grid = center_lat + row_offsets[:, None] + jitter
    lon_grid = center_lon + col_offsets[None, :] + jitter

    chl_field = 1.0 + 0.3 * np.sin(np.linspace(0, 3.0, n_lines))[:, None] + 0.1 * rng.normal(
        size=(n_lines, n_pixels)
    )
    chl_field = np.clip(chl_field, 0.2, 5.0)

    rrs_bands = {}
    for wl in wavelengths:
        band_cube = np.empty((n_lines, n_pixels), dtype=np.float32)
        for i in range(n_lines):
            for j in range(n_pixels):
                base = _rrs_spectrum_shape(np.array([wl]), chlorophyll_like=chl_field[i, j])[0]
                band_cube[i, j] = base + rng.normal(scale=0.00015)
        rrs_bands[int(wl)] = band_cube

    l2_flags = np.zeros((n_lines, n_pixels), dtype=np.int32)
    ATMFAIL, LAND, CLDICE = 1 << 0, 1 << 1, 1 << 9
    n_cloud = int(round(cloud_fraction * n_lines * n_pixels))
    if n_cloud > 0:
        flat_indices = rng.choice(n_lines * n_pixels, size=n_cloud, replace=False)
        for flat in flat_indices:
            i, j = divmod(int(flat), n_pixels)
            l2_flags[i, j] |= CLDICE
            for wl in rrs_bands:
                rrs_bands[wl][i, j] = np.nan
    if land_corner:
        l2_flags[0:3, 0:3] |= LAND
        for wl in rrs_bands:
            rrs_bands[wl][0:3, 0:3] = np.nan

    year = np.full(n_lines, acquisition_time.year, dtype=np.int32)
    day_of_year = np.full(n_lines, acquisition_time.timetuple().tm_yday, dtype=np.int32)
    base_msec = (
        acquisition_time.hour * 3600_000
        + acquisition_time.minute * 60_000
        + acquisition_time.second * 1000
    )
    msec = (base_msec + np.arange(n_lines) * 150).astype(np.float64)

    coverage_start = acquisition_time
    coverage_end = acquisition_time + _dt.timedelta(seconds=n_lines * 0.15)

    with netCDF4.Dataset(path, mode="w", format="NETCDF4") as ds:
        ds.platform = platform
        ds.instrument = instrument
        ds.title = f"{platform} {instrument} Level-2 Data (synthetic test granule)"
        ds.processing_version = "synthetic-0.1"
        ds.time_coverage_start = coverage_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        ds.time_coverage_end = coverage_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        ds.createDimension("number_of_lines", n_lines)
        ds.createDimension("pixels_per_line", n_pixels)

        nav = ds.createGroup("navigation_data")
        lon_var = nav.createVariable("longitude", "f4", ("number_of_lines", "pixels_per_line"))
        lat_var = nav.createVariable("latitude", "f4", ("number_of_lines", "pixels_per_line"))
        lon_var[:, :] = lon_grid
        lat_var[:, :] = lat_grid

        sbp = ds.createGroup("sensor_band_parameters")
        ds.createDimension("wavelength_dim", n_bands)
        wl_var = sbp.createVariable("wavelength", "f4", ("wavelength_dim",))
        wl_var[:] = wavelengths

        geo = ds.createGroup("geophysical_data")
        for wl in sorted(rrs_bands):
            var = geo.createVariable(
                f"Rrs_{wl}",
                "f4",
                ("number_of_lines", "pixels_per_line"),
                fill_value=np.float32(np.nan),
            )
            var[:, :] = rrs_bands[wl]
            var.units = "sr^-1"
            var.long_name = f"Remote sensing reflectance at {wl} nm"

        flag_var = geo.createVariable("l2_flags", "i4", ("number_of_lines", "pixels_per_line"))
        flag_var[:, :] = l2_flags
        flag_var.flag_meanings = "ATMFAIL LAND SPARE SPARE2 SPARE3 SPARE4 SPARE5 SPARE6 SPARE7 CLDICE"
        flag_var.flag_masks = np.array(
            [1 << 0, 1 << 1, 1 << 2, 1 << 3, 1 << 4, 1 << 5, 1 << 6, 1 << 7, 1 << 8, 1 << 9],
            dtype=np.int32,
        )

        sla = ds.createGroup("scan_line_attributes")
        year_var = sla.createVariable("year", "i4", ("number_of_lines",))
        day_var = sla.createVariable("day", "i4", ("number_of_lines",))
        msec_var = sla.createVariable("msec", "f8", ("number_of_lines",))
        year_var[:] = year
        day_var[:] = day_of_year
        msec_var[:] = msec

    return path
