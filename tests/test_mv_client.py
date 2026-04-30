# tests/test_mv_client.py
from unittest.mock import patch, MagicMock
import pytest

import _mv_client as MV


def _mock_response(json_payload, status=200, headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_payload
    r.headers = headers or {}
    r.text = str(json_payload)
    return r


def test_verify_returns_canonical_status_ok():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"result": "ok", "email": "x@y.com"})
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "ok"
    assert result["email"] == "x@y.com"


def test_verify_maps_catch_all_status():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"result": "catch_all"})
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "catch_all"


def test_verify_maps_invalid_disposable_unknown():
    for raw in ["invalid", "disposable", "unknown"]:
        with patch("_mv_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response({"result": raw})
            result = MV.verify("x@y.com", api_key="fake")
        assert result["status"] == raw, f"failed for {raw}"


def test_verify_unknown_provider_status_maps_to_error():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"result": "weird_new_value"})
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "error"


def test_verify_retries_on_timeout_then_succeeds():
    import requests as req
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.side_effect = [
            req.exceptions.Timeout("timeout"),
            _mock_response({"result": "ok"}),
        ]
        with patch("_mv_client.time.sleep"):
            result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "ok"
    assert mock_get.call_count == 2


def test_verify_returns_error_after_max_retries():
    import requests as req
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.side_effect = req.exceptions.ConnectionError("boom")
        with patch("_mv_client.time.sleep"):
            result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "error"


def test_verify_aborts_on_401():
    with patch("_mv_client.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"error": "bad key"}, status=401)
        with pytest.raises(MV.MVAuthError):
            MV.verify("x@y.com", api_key="fake")


def test_verify_respects_retry_after_on_429():
    with patch("_mv_client.requests.get") as mock_get, \
         patch("_mv_client.time.sleep") as mock_sleep:
        mock_get.side_effect = [
            _mock_response({"error": "rate limited"}, status=429, headers={"Retry-After": "2"}),
            _mock_response({"result": "ok"}),
        ]
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "ok"
    mock_sleep.assert_any_call(2)


def test_verify_handles_non_json_200_response():
    """A 200 OK with malformed body should return an error dict, not crash."""
    with patch("_mv_client.requests.get") as mock_get:
        bad = MagicMock()
        bad.status_code = 200
        bad.json.side_effect = ValueError("not json")
        bad.text = "<html>maintenance</html>"
        bad.headers = {}
        mock_get.return_value = bad
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "error"
    assert "non-json" in result["raw"].get("error", "").lower() or "json" in result["raw"].get("error", "").lower()


def test_verify_retry_after_with_http_date_falls_back_to_default():
    """Retry-After can be HTTP-date format per RFC 7231 — should not crash."""
    with patch("_mv_client.requests.get") as mock_get, \
         patch("_mv_client.time.sleep") as mock_sleep:
        mock_get.side_effect = [
            _mock_response({"err": "rate limited"}, status=429,
                           headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
            _mock_response({"result": "ok"}),
        ]
        result = MV.verify("x@y.com", api_key="fake")
    assert result["status"] == "ok"
    # Should have slept the default fallback (5s), not crashed
    mock_sleep.assert_any_call(5)
