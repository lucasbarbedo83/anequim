import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from anequim.core.exceptions import DownloadNotAvailableError


def test_get_access_token_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("CDSE_USERNAME", raising=False)
    monkeypatch.delenv("CDSE_PASSWORD", raising=False)
    from anequim.download.copernicus import get_access_token

    with pytest.raises(DownloadNotAvailableError):
        get_access_token()


def _fake_safe_zip_bytes(name: str = "S3A_OL_2_WFR_fake.SEN3") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{name}/xfdumanifest.xml", "<xfdu/>")
        zf.writestr(f"{name}/geo_coordinates.nc", "fake-binary-content")
    return buf.getvalue()


def test_fetch_olci_granules_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("CDSE_USERNAME", "fake_user")
    monkeypatch.setenv("CDSE_PASSWORD", "fake_pass")

    zip_bytes = _fake_safe_zip_bytes()

    search_response = MagicMock()
    search_response.raise_for_status = lambda: None
    search_response.json = lambda: {"value": [{"Id": "abc123", "Name": "S3A_OL_2_WFR_fake.SEN3"}]}

    token_response = MagicMock()
    token_response.raise_for_status = lambda: None
    token_response.json = lambda: {"access_token": "FAKE_TOKEN"}

    class FakeStreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield zip_bytes

    calls = {"get": [], "post": []}

    def fake_get(url, **kwargs):
        calls["get"].append((url, kwargs))
        if url.endswith("/Products"):
            return search_response
        return FakeStreamResponse()

    def fake_post(url, **kwargs):
        calls["post"].append((url, kwargs))
        return token_response

    with patch("requests.get", side_effect=fake_get), patch("requests.post", side_effect=fake_post):
        from anequim.download.copernicus import fetch_olci_granules

        paths = fetch_olci_granules(
            longitude=-70.5,
            latitude=41.3,
            target_time="2024-06-15T15:00:00Z",
            cache_dir=str(tmp_path),
        )

    assert len(paths) == 1
    assert os.path.isdir(paths[0])
    assert os.path.isfile(os.path.join(paths[0], "xfdumanifest.xml"))

    # Confirm the search request encodes a sane spatial/temporal filter.
    search_call = next(c for c in calls["get"] if c[0].endswith("/Products"))
    filter_str = search_call[1]["params"]["$filter"]
    assert "SENTINEL-3" in filter_str
    assert "OL_2_WFR___" in filter_str
    assert "Intersects" in filter_str

    # A second call for the same product should reuse the cached
    # extraction rather than re-downloading.
    with patch("requests.get", side_effect=fake_get) as get_mock, patch(
        "requests.post", side_effect=fake_post
    ):
        from anequim.download.copernicus import fetch_olci_granules as fetch_again

        paths_2 = fetch_again(
            longitude=-70.5,
            latitude=41.3,
            target_time="2024-06-15T15:00:00Z",
            cache_dir=str(tmp_path),
        )
    assert paths_2 == paths
    # Only the search call should have happened, no re-download.
    download_calls = [c for c in get_mock.call_args_list if "/Products(" in c.args[0]]
    assert len(download_calls) == 0


def test_fetch_olci_granules_no_results_returns_empty_list(monkeypatch, tmp_path):
    monkeypatch.setenv("CDSE_USERNAME", "fake_user")
    monkeypatch.setenv("CDSE_PASSWORD", "fake_pass")

    empty_response = MagicMock()
    empty_response.raise_for_status = lambda: None
    empty_response.json = lambda: {"value": []}

    with patch("requests.get", return_value=empty_response):
        from anequim.download.copernicus import fetch_olci_granules

        paths = fetch_olci_granules(
            longitude=-70.5,
            latitude=41.3,
            target_time="2024-06-15T15:00:00Z",
            cache_dir=str(tmp_path),
        )
    assert paths == []


def test_fetch_granules_dispatches_olci_to_copernicus(monkeypatch, tmp_path):
    with patch("anequim.download.fetch_olci_granules", return_value=["/fake/path.SEN3"]) as mock_fn:
        from anequim.download import fetch_granules

        result = fetch_granules(
            sensor="OLCI",
            longitude=-70.5,
            latitude=41.3,
            target_time="2024-06-15T15:00:00Z",
        )
    assert result == ["/fake/path.SEN3"]
    assert mock_fn.called
