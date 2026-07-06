"""Generate a small, structurally-realistic synthetic PACE OCI L2
OC_AOP granule for testing and demos, without needing network access to
a real NASA OB.DAAC file.

The synthetic file reproduces the group/variable layout that
:class:`anequim.readers.pace_oci.PaceOciL2Reader` expects (navigation_data,
sensor_band_parameters, geophysical_data, scan_line_attributes, plus the
relevant global attributes), with a plausible phytoplankton-influenced
Rrs spectral shape (a green/blue peak with red absorption) and a
scattering of flagged pixels (simulated cloud/land) so QC logic has
something real to filter.

Requires the ``netCDF4`` package (a core anequim dependency).
"""

from __future__ import annotations

import datetime as _dt
from typing import Tuple

import numpy as np


def _rrs_spectrum_shape(wavelengths: np.ndarray, chlorophyll_like: float = 1.0) -> np.ndarray:
    """A stylized, phytoplankton-influenced Rrs spectral shape: a
    blue-green peak (~555 nm) with reduced blue reflectance (chlorophyll
    absorption) and reduced red/NIR reflectance (water absorption).
    Purely illustrative — not a validated bio-optical model.
    """
    peak = 555.0 - 40.0 * np.tanh(chlorophyll_like - 1.0)
    width = 55.0
    shape = np.exp(-0.5 * ((wavelengths - peak) / width) ** 2)
    blue_dip = 1.0 - 0.35 * np.exp(-0.5 * ((wavelengths - 440.0) / 25.0) ** 2) * min(
        chlorophyll_like, 2.0
    )
    red_falloff = np.exp(-np.clip(wavelengths - 600.0, 0, None) / 120.0)
    return 0.008 * shape * blue_dip * red_falloff


def make_synthetic_pace_oci_file(
    path: str,
    center_lon: float = -70.5,
    center_lat: float = 41.3,
    n_lines: int = 20,
    n_pixels: int = 20,
    n_bands: int = 12,
    wavelength_range: Tuple[float, float] = (400.0, 700.0),
    pixel_spacing_deg: float = 0.01,
    acquisition_time: "_dt.datetime | None" = None,
    cloud_fraction: float = 0.1,
    land_corner: bool = True,
    seed: int = 0,
) -> str:
    """Write a synthetic PACE OCI L2 OC_AOP-shaped NetCDF file to ``path``.

    Returns ``path`` for convenience.
    """
    import netCDF4

    rng = np.random.default_rng(seed)

    if acquisition_time is None:
        acquisition_time = _dt.datetime(2024, 6, 15, 14, 42, 0, tzinfo=_dt.timezone.utc)

    wavelengths = np.linspace(wavelength_range[0], wavelength_range[1], n_bands)

    # Simple curvilinear-looking grid: mostly regular, with tiny jitter to
    # mimic a real satellite swath's non-rectilinear geolocation.
    row_offsets = (np.arange(n_lines) - n_lines / 2) * pixel_spacing_deg
    col_offsets = (np.arange(n_pixels) - n_pixels / 2) * pixel_spacing_deg
    jitter = rng.normal(scale=pixel_spacing_deg * 0.02, size=(n_lines, n_pixels))
    lat_grid = center_lat + row_offsets[:, None] + jitter
    lon_grid = center_lon + col_offsets[None, :] + jitter

    # Slowly-varying "chlorophyll-like" field so the ROI isn't perfectly
    # uniform (gives CV-based QC something non-trivial to compute).
    chl_field = 1.0 + 0.3 * np.sin(np.linspace(0, 3.0, n_lines))[:, None] + 0.1 * rng.normal(
        size=(n_lines, n_pixels)
    )
    chl_field = np.clip(chl_field, 0.2, 5.0)

    rrs_cube = np.empty((n_lines, n_pixels, n_bands), dtype=np.float32)
    for i in range(n_lines):
        for j in range(n_pixels):
            base = _rrs_spectrum_shape(wavelengths, chlorophyll_like=chl_field[i, j])
            noise = rng.normal(scale=0.00015, size=n_bands)
            rrs_cube[i, j, :] = base + noise

    l2_flags = np.zeros((n_lines, n_pixels), dtype=np.int32)
    ATMFAIL, LAND, HIGLINT, CLDICE = 1 << 0, 1 << 1, 1 << 3, 1 << 9

    n_cloud = int(round(cloud_fraction * n_lines * n_pixels))
    if n_cloud > 0:
        flat_indices = rng.choice(n_lines * n_pixels, size=n_cloud, replace=False)
        for flat in flat_indices:
            i, j = divmod(int(flat), n_pixels)
            l2_flags[i, j] |= CLDICE
            rrs_cube[i, j, :] = np.nan

    if land_corner:
        l2_flags[0:3, 0:3] |= LAND
        rrs_cube[0:3, 0:3, :] = np.nan

    year = np.full(n_lines, acquisition_time.year, dtype=np.int32)
    day_of_year = np.full(n_lines, acquisition_time.timetuple().tm_yday, dtype=np.int32)
    base_msec = (
        acquisition_time.hour * 3600_000
        + acquisition_time.minute * 60_000
        + acquisition_time.second * 1000
    )
    msec = (base_msec + np.arange(n_lines) * 150).astype(np.float64)  # ~150 ms per scan line

    coverage_start = acquisition_time
    coverage_end = acquisition_time + _dt.timedelta(seconds=n_lines * 0.15)

    with netCDF4.Dataset(path, mode="w", format="NETCDF4") as ds:
        ds.platform = "PACE"
        ds.instrument = "OCI"
        ds.title = "PACE OCI Level-2 Data (synthetic test granule)"
        ds.processing_version = "synthetic-0.1"
        ds.time_coverage_start = coverage_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        ds.time_coverage_end = coverage_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        ds.createDimension("number_of_lines", n_lines)
        ds.createDimension("pixels_per_line", n_pixels)
        ds.createDimension("wavelength_3d", n_bands)

        nav = ds.createGroup("navigation_data")
        lon_var = nav.createVariable("longitude", "f4", ("number_of_lines", "pixels_per_line"))
        lat_var = nav.createVariable("latitude", "f4", ("number_of_lines", "pixels_per_line"))
        lon_var[:, :] = lon_grid
        lat_var[:, :] = lat_grid
        lon_var.units = "degrees_east"
        lat_var.units = "degrees_north"

        sbp = ds.createGroup("sensor_band_parameters")
        wl_var = sbp.createVariable("wavelength_3d", "f4", ("wavelength_3d",))
        wl_var[:] = wavelengths
        wl_var.units = "nm"

        geo = ds.createGroup("geophysical_data")
        rrs_var = geo.createVariable(
            "Rrs",
            "f4",
            ("number_of_lines", "pixels_per_line", "wavelength_3d"),
            fill_value=np.float32(np.nan),
        )
        rrs_var[:, :, :] = rrs_cube
        rrs_var.units = "sr^-1"
        rrs_var.long_name = "Remote sensing reflectance"

        flag_var = geo.createVariable("l2_flags", "i4", ("number_of_lines", "pixels_per_line"))
        flag_var[:, :] = l2_flags
        flag_var.flag_meanings = "ATMFAIL LAND SPARE HIGLINT SPARE2 SPARE3 SPARE4 SPARE5 SPARE6 CLDICE"
        flag_var.flag_masks = np.array(
            [1 << 0, 1 << 1, 1 << 2, 1 << 3, 1 << 4, 1 << 5, 1 << 6, 1 << 7, 1 << 8, 1 << 9],
            dtype=np.int32,
        )

        aot_var = geo.createVariable("aot_865", "f4", ("number_of_lines", "pixels_per_line"))
        aot_var[:, :] = 0.05 + 0.01 * rng.normal(size=(n_lines, n_pixels))

        angstrom_var = geo.createVariable("angstrom", "f4", ("number_of_lines", "pixels_per_line"))
        angstrom_var[:, :] = 1.1 + 0.05 * rng.normal(size=(n_lines, n_pixels))

        sla = ds.createGroup("scan_line_attributes")
        year_var = sla.createVariable("year", "i4", ("number_of_lines",))
        day_var = sla.createVariable("day", "i4", ("number_of_lines",))
        msec_var = sla.createVariable("msec", "f8", ("number_of_lines",))
        year_var[:] = year
        day_var[:] = day_of_year
        msec_var[:] = msec

    return path
