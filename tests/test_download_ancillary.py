import sys
import types

import numpy as np
import pytest

from anequim.core.exceptions import DownloadNotAvailableError


def _fake_earthaccess(monkeypatch, search_return, download_return):
    fake = types.ModuleType("earthaccess")
    fake.search_data = lambda **kwargs: search_return
    fake.download = lambda results, directory: download_return(directory)
    monkeypatch.setitem(sys.modules, "earthaccess", fake)
    return fake


def _fake_netcdf4_ozone(monkeypatch, ozone_du: float):
    """Inject a fake netCDF4 module whose Dataset context-manager yields
    a nested HDFEOS/GRIDS/.../Data Fields group tree matching OMTO3d,
    with a uniform ozone field."""

    class _FakeVar:
        def __init__(self, arr):
            self._arr = arr

        def __getitem__(self, idx):
            return self._arr

    class _FakeGroup:
        def __init__(self, groups=None, variables=None):
            self.groups = groups or {}
            self.variables = variables or {}

    def _make_ds():
        grid = np.full((180, 360), ozone_du)
        data_fields = _FakeGroup(variables={"ColumnAmountO3": _FakeVar(grid)})
        o3_group = _FakeGroup(groups={"Data Fields": data_fields})
        grids = _FakeGroup(groups={"OMI Column Amount O3": o3_group})
        hdfeos = _FakeGroup(groups={"GRIDS": grids})
        return _FakeGroup(groups={"HDFEOS": hdfeos})

    class _FakeDataset:
        def __init__(self, path, mode="r"):
            self._ds = _make_ds()

        def __enter__(self):
            return self._ds

        def __exit__(self, *exc):
            return False

    fake_netcdf4 = types.ModuleType("netCDF4")
    fake_netcdf4.Dataset = _FakeDataset
    monkeypatch.setitem(sys.modules, "netCDF4", fake_netcdf4)


def test_fetch_ozone_omi_without_earthaccess_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "earthaccess", None)
    from anequim.download.ancillary import fetch_ozone_omi

    with pytest.raises(DownloadNotAvailableError):
        fetch_ozone_omi(longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z")


def test_fetch_ozone_omi_no_granule_found_raises(monkeypatch):
    _fake_earthaccess(monkeypatch, search_return=[], download_return=lambda d: [])
    from anequim.download.ancillary import fetch_ozone_omi

    with pytest.raises(DownloadNotAvailableError):
        fetch_ozone_omi(longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z")


def test_fetch_ozone_omi_returns_expected_value(monkeypatch, tmp_path):
    _fake_earthaccess(
        monkeypatch,
        search_return=["granule-1"],
        download_return=lambda d: [f"{d}/fake_omto3d.nc"],
    )
    _fake_netcdf4_ozone(monkeypatch, ozone_du=287.5)
    from anequim.download.ancillary import fetch_ozone_omi, OMTO3D_SHORT_NAME

    value = fetch_ozone_omi(
        longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z", cache_dir=str(tmp_path)
    )
    assert value == pytest.approx(287.5)


def test_fetch_atmospheric_ancillary_combines_ozone_and_meteorology(monkeypatch, tmp_path):
    """fetch_atmospheric_ancillary should call both the ozone and MERRA-2
    fetchers and merge their results into one dict — verified here by
    monkeypatching the two sub-fetchers directly rather than the whole
    network stack, since that's the actual integration point."""
    import anequim.download.ancillary as ancillary

    monkeypatch.setattr(ancillary, "fetch_ozone_omi", lambda *a, **k: 290.0)
    monkeypatch.setattr(
        ancillary,
        "fetch_merra2_meteorology",
        lambda *a, **k: {"water_vapor_cm": 2.3, "surface_pressure_hpa": 1012.0},
    )

    result = ancillary.fetch_atmospheric_ancillary(
        longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z", cache_dir=str(tmp_path)
    )
    assert result == {
        "ozone_du": 290.0,
        "water_vapor_cm": 2.3,
        "surface_pressure_hpa": 1012.0,
    }


def test_retrieval_config_include_ancillary_atmosphere_default_false():
    from anequim.core.config import RetrievalConfig

    config = RetrievalConfig(
        longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z"
    )
    assert config.include_ancillary_atmosphere is False

    config2 = RetrievalConfig(
        longitude=-70.5,
        latitude=41.3,
        target_time="2024-06-15T15:00:00Z",
        include_ancillary_atmosphere=True,
    )
    assert config2.include_ancillary_atmosphere is True
