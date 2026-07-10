import io
import os
import sys
import types
import zipfile
from unittest.mock import patch

import pytest

from anequim.core.exceptions import DownloadNotAvailableError


def _fake_eumdac_module(product_names=("S3A_OL_2_WFR_fake.SEN3",)):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr(f"{product_names[0]}/xfdumanifest.xml", "<xfdu/>")
        zf.writestr(f"{product_names[0]}/geo_coordinates.nc", "fake-content")
    zip_bytes = zip_buf.getvalue()

    class FakeProduct:
        def __init__(self, name):
            self._name = name

        def __str__(self):
            return self._name

        def open(self):
            return io.BytesIO(zip_bytes)

    class FakeCollection:
        def __init__(self, collection_id):
            self.collection_id = collection_id

        def search(self, **kwargs):
            self.last_search_kwargs = kwargs
            return [FakeProduct(name) for name in product_names]

    class FakeDataStore:
        def __init__(self, token):
            self.token = token

        def get_collection(self, collection_id):
            self._collection = FakeCollection(collection_id)
            return self._collection

    class FakeAccessToken:
        def __init__(self, credentials):
            self.credentials = credentials

    module = types.ModuleType("eumdac")
    module.AccessToken = FakeAccessToken
    module.DataStore = FakeDataStore
    return module


def test_fetch_olci_granules_eumdac_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("EUMETSAT_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("EUMETSAT_CONSUMER_SECRET", raising=False)
    monkeypatch.setitem(sys.modules, "eumdac", _fake_eumdac_module())

    from anequim.download.eumetsat import fetch_olci_granules

    with pytest.raises(DownloadNotAvailableError):
        fetch_olci_granules(longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z")


def test_fetch_olci_granules_eumdac_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("EUMETSAT_CONSUMER_KEY", "fake_key")
    monkeypatch.setenv("EUMETSAT_CONSUMER_SECRET", "fake_secret")
    monkeypatch.setitem(sys.modules, "eumdac", _fake_eumdac_module())

    from anequim.download.eumetsat import fetch_olci_granules

    paths = fetch_olci_granules(
        longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z", cache_dir=str(tmp_path)
    )
    assert len(paths) == 1
    assert os.path.isfile(os.path.join(paths[0], "xfdumanifest.xml"))


def test_fetch_granules_default_olci_backend_is_eumdac():
    with patch(
        "anequim.download.fetch_olci_granules_eumdac", return_value=["/fake/eumdac.SEN3"]
    ) as mock_eumdac, patch(
        "anequim.download.fetch_olci_granules_cdse", return_value=["/fake/cdse.SEN3"]
    ) as mock_cdse:
        from anequim.download import fetch_granules

        result = fetch_granules(
            sensor="OLCI", longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z"
        )
    assert result == ["/fake/eumdac.SEN3"]
    assert mock_eumdac.called
    assert not mock_cdse.called


def test_fetch_granules_olci_backend_override_to_cdse():
    with patch(
        "anequim.download.fetch_olci_granules_cdse", return_value=["/fake/cdse.SEN3"]
    ) as mock_cdse:
        from anequim.download import fetch_granules

        result = fetch_granules(
            sensor="OLCI",
            longitude=-70.5,
            latitude=41.3,
            target_time="2024-06-15T15:00:00Z",
            backend="cdse",
        )
    assert result == ["/fake/cdse.SEN3"]
    assert mock_cdse.called


def test_fetch_granules_modis_default_platform_is_aqua():
    with patch("anequim.download.fetch_modis_granules", return_value=["/fake/modis.nc"]) as mock_fn:
        from anequim.download import fetch_granules

        fetch_granules(sensor="MODIS", longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z")
    assert mock_fn.call_args.kwargs["platform"] == "Aqua"


def test_fetch_granules_modis_terra_alias_routes_platform():
    with patch("anequim.download.fetch_modis_granules", return_value=["/fake/modis.nc"]) as mock_fn:
        from anequim.download import fetch_granules

        fetch_granules(
            sensor="modis-terra", longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z"
        )
    assert mock_fn.call_args.kwargs["platform"] == "Terra"


def test_fetch_granules_viirs_default_platform_is_snpp():
    with patch("anequim.download.fetch_viirs_granules", return_value=["/fake/viirs.nc"]) as mock_fn:
        from anequim.download import fetch_granules

        fetch_granules(sensor="VIIRS", longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z")
    assert mock_fn.call_args.kwargs["platform"] == "SNPP"


def test_fetch_modis_granules_invalid_platform_raises():
    from anequim.download.earthdata import fetch_modis_granules

    with pytest.raises(ValueError):
        fetch_modis_granules(
            longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z", platform="Bogus"
        )


def test_fetch_viirs_granules_invalid_platform_raises():
    from anequim.download.earthdata import fetch_viirs_granules

    with pytest.raises(ValueError):
        fetch_viirs_granules(
            longitude=-70.5, latitude=41.3, target_time="2024-06-15T15:00:00Z", platform="Bogus"
        )
