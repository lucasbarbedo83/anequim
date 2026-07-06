"""Shared pytest fixtures."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

from make_synthetic_pace_file import make_synthetic_pace_oci_file  # noqa: E402

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
