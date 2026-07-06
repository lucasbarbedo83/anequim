import sys
import types

import pytest

from anequim.core.exceptions import DownloadNotAvailableError


def test_fetch_granules_unsupported_sensor_raises():
    from anequim.download import fetch_granules

    with pytest.raises(DownloadNotAvailableError):
        fetch_granules(
            sensor="MODIS",
            longitude=-70.5,
            latitude=41.3,
            target_time="2024-06-15T15:00:00Z",
        )


def test_fetch_olci_granules_raises_not_available():
    from anequim.download.copernicus import fetch_olci_granules

    with pytest.raises(DownloadNotAvailableError):
        fetch_olci_granules(
            longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z"
        )


def test_fetch_pace_oci_granules_without_earthaccess_raises(monkeypatch):
    # Ensure a real earthaccess import isn't accidentally present/importable.
    monkeypatch.setitem(sys.modules, "earthaccess", None)
    from anequim.download.earthdata import fetch_pace_oci_granules

    with pytest.raises(DownloadNotAvailableError):
        fetch_pace_oci_granules(
            longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z"
        )


def test_fetch_pace_oci_granules_calls_earthaccess_correctly(monkeypatch, tmp_path):
    """Inject a fake `earthaccess` module so we can verify anequim builds
    the right search/download calls without needing real network access
    or NASA Earthdata credentials.
    """
    calls = {}

    fake_earthaccess = types.ModuleType("earthaccess")

    def fake_search_data(short_name, temporal, bounding_box, count):
        calls["short_name"] = short_name
        calls["temporal"] = temporal
        calls["bounding_box"] = bounding_box
        calls["count"] = count
        return ["granule-1", "granule-2"]

    def fake_download(results, directory):
        calls["download_results"] = results
        calls["download_directory"] = directory
        return [f"{directory}/{r}.nc" for r in results]

    fake_earthaccess.search_data = fake_search_data
    fake_earthaccess.download = fake_download

    monkeypatch.setitem(sys.modules, "earthaccess", fake_earthaccess)

    from anequim.download.earthdata import fetch_pace_oci_granules, PACE_OCI_AOP_SHORT_NAME

    paths = fetch_pace_oci_granules(
        longitude=-70.5,
        latitude=41.3,
        target_time="2024-06-15T15:00:00Z",
        time_window_hours=2.0,
        cache_dir=str(tmp_path),
        padding_deg=0.25,
        count=5,
    )

    assert calls["short_name"] == PACE_OCI_AOP_SHORT_NAME
    assert calls["count"] == 5
    start, end = calls["temporal"]
    assert start < end
    lon_min, lat_min, lon_max, lat_max = calls["bounding_box"]
    assert lon_min == pytest.approx(-70.75)
    assert lon_max == pytest.approx(-70.25)
    assert lat_min == pytest.approx(41.05)
    assert lat_max == pytest.approx(41.55)
    assert paths == [f"{tmp_path}/granule-1.nc", f"{tmp_path}/granule-2.nc"]


def test_fetch_pace_oci_granules_no_results_returns_empty_list(monkeypatch, tmp_path):
    fake_earthaccess = types.ModuleType("earthaccess")
    fake_earthaccess.search_data = lambda **kwargs: []
    fake_earthaccess.download = lambda results, directory: []
    monkeypatch.setitem(sys.modules, "earthaccess", fake_earthaccess)

    from anequim.download.earthdata import fetch_pace_oci_granules

    paths = fetch_pace_oci_granules(
        longitude=-70.5,
        latitude=41.3,
        target_time="2024-06-15T15:00:00Z",
        cache_dir=str(tmp_path),
    )
    assert paths == []
