"""Generate a small, structurally-realistic synthetic Sentinel-3 OLCI L2
WFR SAFE granule *directory* for testing/demos, without needing network
access to a real Copernicus/EUMETSAT product.

Reproduces the multi-file directory layout
:class:`anequim.readers.olci.OlciL2Reader` expects: an
``xfdumanifest.xml`` marker, ``geo_coordinates.nc``, one
``Oa##_reflectance.nc`` per usable band (written with ``units="1"``, the
pre-Collection-4 water-leaving-reflectance convention, so the reader's
rho_w -> Rrs conversion path gets exercised), and ``wqsf.nc`` with a
handful of named flag bits.

Requires the ``netCDF4`` package.
"""

from __future__ import annotations

import datetime as _dt
import os

import numpy as np

from make_synthetic_pace_file import _rrs_spectrum_shape  # reuse the same spectral shape helper

from anequim.readers.olci import OLCI_RRS_BANDS


def make_synthetic_olci_wfr_directory(
    path: str,
    center_lon: float = -70.5,
    center_lat: float = 41.3,
    n_rows: int = 20,
    n_cols: int = 20,
    pixel_spacing_deg: float = 0.003,  # ~300 m, matching OLCI's nominal resolution
    acquisition_time: "_dt.datetime | None" = None,
    cloud_fraction: float = 0.1,
    seed: int = 0,
) -> str:
    """Write a synthetic OLCI L2 WFR SAFE granule directory at ``path``.

    Returns ``path`` for convenience.
    """
    import netCDF4

    rng = np.random.default_rng(seed)
    os.makedirs(path, exist_ok=True)

    if acquisition_time is None:
        acquisition_time = _dt.datetime(2024, 6, 15, 14, 42, 0, tzinfo=_dt.timezone.utc)
    coverage_end = acquisition_time + _dt.timedelta(seconds=n_rows * 0.044)  # ~44 ms/line at 300m

    # SAFE manifest marker (content is irrelevant to the reader; only its
    # presence matters, per resolve_files()/OlciL2Reader.matches()).
    with open(os.path.join(path, "xfdumanifest.xml"), "w") as fh:
        fh.write("<xfdu:XFDU xmlns:xfdu='http://www.esa.int/safe/sentinel/1.1'/>\n")

    row_offsets = (np.arange(n_rows) - n_rows / 2) * pixel_spacing_deg
    col_offsets = (np.arange(n_cols) - n_cols / 2) * pixel_spacing_deg
    jitter = rng.normal(scale=pixel_spacing_deg * 0.02, size=(n_rows, n_cols))
    lat_grid = center_lat + row_offsets[:, None] + jitter
    lon_grid = center_lon + col_offsets[None, :] + jitter

    def _write_time_attrs(ds):
        ds.start_time = acquisition_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        ds.stop_time = coverage_end.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    with netCDF4.Dataset(os.path.join(path, "geo_coordinates.nc"), mode="w", format="NETCDF4") as ds:
        ds.createDimension("rows", n_rows)
        ds.createDimension("columns", n_cols)
        lon_var = ds.createVariable("longitude", "f4", ("rows", "columns"))
        lat_var = ds.createVariable("latitude", "f4", ("rows", "columns"))
        lon_var[:, :] = lon_grid
        lat_var[:, :] = lat_grid
        ds.platform = "Sentinel-3A"
        ds.references = "OL__L2M.003.00 (synthetic test granule)"
        _write_time_attrs(ds)

    # Slowly-varying chlorophyll-like field for a non-trivial CV.
    chl_field = 1.0 + 0.3 * np.sin(np.linspace(0, 3.0, n_rows))[:, None] + 0.1 * rng.normal(
        size=(n_rows, n_cols)
    )
    chl_field = np.clip(chl_field, 0.2, 5.0)

    band_numbers = sorted(OLCI_RRS_BANDS)
    for n in band_numbers:
        wl = OLCI_RRS_BANDS[n]
        rho_w = np.empty((n_rows, n_cols), dtype=np.float32)
        for i in range(n_rows):
            for j in range(n_cols):
                # _rrs_spectrum_shape returns Rrs-scale values; multiply by
                # pi to synthesize the rho_w convention this file uses.
                rrs_val = _rrs_spectrum_shape(np.array([wl]), chlorophyll_like=chl_field[i, j])[0]
                rho_w[i, j] = rrs_val * np.pi + rng.normal(scale=0.0005)

        with netCDF4.Dataset(
            os.path.join(path, f"Oa{n:02d}_reflectance.nc"), mode="w", format="NETCDF4"
        ) as ds:
            ds.createDimension("rows", n_rows)
            ds.createDimension("columns", n_cols)
            var = ds.createVariable(
                f"Oa{n:02d}_reflectance", "f4", ("rows", "columns"), fill_value=np.float32(np.nan)
            )
            var[:, :] = rho_w
            var.units = "1"  # dimensionless water-leaving reflectance (pre-Collection-4 convention)

    wqsf = np.zeros((n_rows, n_cols), dtype=np.uint32)
    flag_names = ["INVALID", "LAND", "CLOUD", "CLOUD_AMBIGUOUS", "SUSPECT", "AC_FAIL"]
    flag_masks = np.array([1 << i for i in range(len(flag_names))], dtype=np.uint32)

    n_cloud = int(round(cloud_fraction * n_rows * n_cols))
    if n_cloud > 0:
        flat_indices = rng.choice(n_rows * n_cols, size=n_cloud, replace=False)
        for flat in flat_indices:
            i, j = divmod(int(flat), n_cols)
            wqsf[i, j] |= flag_masks[flag_names.index("CLOUD")]

    wqsf[0:2, 0:2] |= flag_masks[flag_names.index("LAND")]

    with netCDF4.Dataset(os.path.join(path, "wqsf.nc"), mode="w", format="NETCDF4") as ds:
        ds.createDimension("rows", n_rows)
        ds.createDimension("columns", n_cols)
        var = ds.createVariable("WQSF", "u4", ("rows", "columns"))
        var[:, :] = wqsf
        var.flag_meanings = " ".join(flag_names)
        var.flag_masks = flag_masks
        _write_time_attrs(ds)

    with netCDF4.Dataset(os.path.join(path, "w_aer.nc"), mode="w", format="NETCDF4") as ds:
        ds.createDimension("rows", n_rows)
        ds.createDimension("columns", n_cols)
        t865 = ds.createVariable("T865", "f4", ("rows", "columns"))
        a865 = ds.createVariable("A865", "f4", ("rows", "columns"))
        t865[:, :] = 0.05 + 0.01 * rng.normal(size=(n_rows, n_cols))
        a865[:, :] = 1.1 + 0.05 * rng.normal(size=(n_rows, n_cols))

    return path
