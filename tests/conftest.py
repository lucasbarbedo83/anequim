"""Shared pytest fixtures."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

from make_synthetic_pace_file import make_synthetic_pace_oci_file  # noqa: E402
from make_synthetic_olci_directory import make_synthetic_olci_wfr_directory  # noqa: E402
from make_synthetic_obpg_multiband_file import (  # noqa: E402
    make_synthetic_obpg_multiband_file,
    MODIS_AQUA_BANDS,
    VIIRS_SNPP_BANDS,
)

CENTER_LON = -70.5
CENTER_LAT = 41.3


@pytest.fixture()
def synthetic_pace_file(tmp_path):
    """Path to a freshly-generated synthetic PACE OCI L2 granule."""
    path = str(tmp_path / "PACE_OCI.20240615T144200.L2.OC_AOP.nc")
    make_synthetic_pace_oci_file(
        path, center_lon=CENTER_LON, center_lat=CENTER_LAT, n_lines=20, n_pixels=20, n_bands=12
    )
    return path


@pytest.fixture()
def synthetic_olci_directory(tmp_path):
    """Path to a freshly-generated synthetic OLCI L2 WFR SAFE directory."""
    path = str(tmp_path / "S3A_OL_2_WFR____20240615T144200_test.SEN3")
    make_synthetic_olci_wfr_directory(
        path, center_lon=CENTER_LON, center_lat=CENTER_LAT, n_rows=20, n_cols=20
    )
    return path


@pytest.fixture()
def synthetic_modis_file(tmp_path):
    """Path to a freshly-generated synthetic MODIS-Aqua L2 OC granule."""
    path = str(tmp_path / "AQUA_MODIS.20240615T144200.L2.OC.nc")
    make_synthetic_obpg_multiband_file(
        path,
        instrument="MODIS",
        platform="Aqua",
        bands=MODIS_AQUA_BANDS,
        center_lon=CENTER_LON,
        center_lat=CENTER_LAT,
    )
    return path


@pytest.fixture()
def synthetic_viirs_file(tmp_path):
    """Path to a freshly-generated synthetic VIIRS-SNPP L2 OC granule."""
    path = str(tmp_path / "SNPP_VIIRS.20240615T144200.L2.OC.nc")
    make_synthetic_obpg_multiband_file(
        path,
        instrument="VIIRS",
        platform="SNPP",
        bands=VIIRS_SNPP_BANDS,
        center_lon=CENTER_LON,
        center_lat=CENTER_LAT,
    )
    return path
