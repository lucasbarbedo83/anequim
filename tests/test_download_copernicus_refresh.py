import os
from unittest.mock import MagicMock, patch

import anequim.download.copernicus as cop


def test_login_caches_refresh_token(monkeypatch, tmp_path):
    cache_path = str(tmp_path / "cdse_refresh_token")
    monkeypatch.setattr(cop, "CDSE_REFRESH_TOKEN_CACHE_PATH", cache_path)
    monkeypatch.setenv("CDSE_USERNAME", "fake_user")
    monkeypatch.setenv("CDSE_PASSWORD", "fake_pass")

    response = MagicMock()
    response.status_code = 200
    response.json = lambda: {"access_token": "ACCESS_1", "refresh_token": "REFRESH_1"}

    with patch("requests.post", return_value=response) as mock_post:
        token = cop.login(totp="123456")

    assert token == "ACCESS_1"
    assert mock_post.call_args.kwargs["data"]["totp"] == "123456"
    assert os.path.isfile(cache_path)
    with open(cache_path) as fh:
        assert fh.read() == "REFRESH_1"


def test_unattended_call_uses_cached_refresh_token_not_password(monkeypatch, tmp_path):
    cache_path = str(tmp_path / "cdse_refresh_token")
    with open(cache_path, "w") as fh:
        fh.write("REFRESH_1")
    monkeypatch.setattr(cop, "CDSE_REFRESH_TOKEN_CACHE_PATH", cache_path)
    monkeypatch.delenv("CDSE_REFRESH_TOKEN", raising=False)

    response = MagicMock()
    response.status_code = 200
    response.json = lambda: {"access_token": "ACCESS_2", "refresh_token": "REFRESH_2"}

    with patch("requests.post", return_value=response) as mock_post:
        token = cop._get_access_token_preferring_refresh()

    assert token == "ACCESS_2"
    call_data = mock_post.call_args.kwargs["data"]
    assert call_data["grant_type"] == "refresh_token"
    assert call_data["refresh_token"] == "REFRESH_1"
    with open(cache_path) as fh:
        assert fh.read() == "REFRESH_2"  # rotated


def test_expired_refresh_token_falls_back_to_password_login(monkeypatch, tmp_path):
    cache_path = str(tmp_path / "cdse_refresh_token")
    with open(cache_path, "w") as fh:
        fh.write("EXPIRED")
    monkeypatch.setattr(cop, "CDSE_REFRESH_TOKEN_CACHE_PATH", cache_path)
    monkeypatch.setenv("CDSE_USERNAME", "fake_user")
    monkeypatch.setenv("CDSE_PASSWORD", "fake_pass")
    monkeypatch.delenv("CDSE_REFRESH_TOKEN", raising=False)

    fail_response = MagicMock()
    fail_response.status_code = 400

    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json = lambda: {"access_token": "FRESH_ACCESS", "refresh_token": "FRESH_REFRESH"}

    grant_types = []

    def fake_post(url, data=None, **kwargs):
        grant_types.append(data.get("grant_type"))
        return fail_response if data.get("grant_type") == "refresh_token" else login_response

    with patch("requests.post", side_effect=fake_post):
        token = cop._get_access_token_preferring_refresh(totp="999999")

    assert token == "FRESH_ACCESS"
    assert grant_types == ["refresh_token", "password"]
