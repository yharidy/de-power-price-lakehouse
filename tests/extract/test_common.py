"""Tests for src/extract/common.py."""

import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import requests

from de_power_price.api import common

# ---------------------------------------------------------------------------
# parse_timestamp_string
# ---------------------------------------------------------------------------


class TestParseTimestampString:
    def test_naive_iso_string_assumed_utc(self):
        result = common.parse_timestamp_string("2026-01-15T12:00:00")
        assert result == datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

    def test_aware_iso_string_converted_to_utc(self):
        # +02:00 -> 10:00 UTC
        result = common.parse_timestamp_string("2026-01-15T12:00:00+02:00")
        assert result == datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

    def test_date_only_string(self):
        result = common.parse_timestamp_string("2026-01-15")
        assert result == datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)

    def test_unix_timestamp_string(self):
        # 2021-01-01T00:00:00Z
        result = common.parse_timestamp_string("1609459200")
        assert result == datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_unix_timestamp_float_string(self):
        result = common.parse_timestamp_string("1609459200.5")
        assert result.year == 2021
        assert result.tzinfo == UTC

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to parse timestamp"):
            common.parse_timestamp_string("not-a-timestamp")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            common.parse_timestamp_string("")


# ---------------------------------------------------------------------------
# RateLimitError / wait_for_retry
# ---------------------------------------------------------------------------

class TestWaitForRetry:
    def _retry_state_with_exception(self, exception):
        state = Mock()
        state.outcome.exception.return_value = exception
        state.attempt_number = 1
        return state

    def test_rate_limit_error_returns_retry_after(self):
        state = self._retry_state_with_exception(common.RateLimitError(17))
        assert common.wait_for_retry(state) == 17

    def test_other_exception_falls_back_to_backoff(self):
        state = self._retry_state_with_exception(requests.ConnectionError())
        wait_seconds = common.wait_for_retry(state)
        assert wait_seconds >= 0

    def test_rate_limit_error_message(self):
        err = common.RateLimitError(5)
        assert "5s" in str(err)
        assert err.retry_after == 5


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------

class TestFetch:
    def test_successful_response_returns_json(self, monkeypatch):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"ok": True}
        monkeypatch.setattr(requests, "get", Mock(return_value=mock_response))

        result = common.fetch("https://example.com", {"a": 1})

        assert result == {"ok": True}
        requests.get.assert_called_once_with(
            "https://example.com", params={"a": 1}, timeout=30
        )

    def test_passes_custom_timeout(self, monkeypatch):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {}
        monkeypatch.setattr(requests, "get", Mock(return_value=mock_response))

        common.fetch("https://example.com", {}, timeout=5)

        _, kwargs = requests.get.call_args
        assert kwargs["timeout"] == 5

    def test_non_429_http_error_raised_immediately_without_retry(self, monkeypatch):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status = Mock(
            side_effect=requests.HTTPError("404 Not Found")
        )
        get_mock = Mock(return_value=mock_response)
        monkeypatch.setattr(requests, "get", get_mock)

        with pytest.raises(requests.HTTPError):
            common.fetch("https://example.com", {})

        # Should not have retried a non-retryable error.
        assert get_mock.call_count == 1

    def test_429_retries_and_eventually_succeeds(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)

        rate_limited = Mock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "1"}

        success = Mock()
        success.status_code = 200
        success.raise_for_status = Mock()
        success.json.return_value = {"ok": True}

        get_mock = Mock(side_effect=[rate_limited, success])
        monkeypatch.setattr(requests, "get", get_mock)

        result = common.fetch("https://example.com", {})

        assert result == {"ok": True}
        assert get_mock.call_count == 2

    def test_429_exhausts_retries_and_raises(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)

        rate_limited = Mock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "0"}
        get_mock = Mock(return_value=rate_limited)
        monkeypatch.setattr(requests, "get", get_mock)

        with pytest.raises(common.RateLimitError):
            common.fetch("https://example.com", {})

        assert get_mock.call_count == 5  # stop_after_attempt(5)

    def test_connection_error_retries(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)

        success = Mock()
        success.status_code = 200
        success.raise_for_status = Mock()
        success.json.return_value = {"ok": True}

        get_mock = Mock(
            side_effect=[requests.ConnectionError("boom"), success]
        )
        monkeypatch.setattr(requests, "get", get_mock)

        result = common.fetch("https://example.com", {})

        assert result == {"ok": True}
        assert get_mock.call_count == 2

    def test_missing_retry_after_header_defaults_to_30(self, monkeypatch):
        state = Mock()
        state.outcome.exception.return_value = common.RateLimitError(30)
        assert common.wait_for_retry(state) == 30


# ---------------------------------------------------------------------------
# write_json
# ---------------------------------------------------------------------------

class TestWriteJson:
    def test_creates_target_dir_and_writes_file(self, tmp_path):
        target_dir = tmp_path / "landing"
        payload = {"a": 1, "b": [1, 2, 3]}

        result_path = common.write_json(payload, target_dir, "data.json")

        assert result_path == target_dir / "data.json"
        assert target_dir.exists()
        with result_path.open() as f:
            assert json.load(f) == payload

    def test_overwrites_existing_file(self, tmp_path, caplog):
        target_dir = tmp_path
        filename = "data.json"

        common.write_json({"version": 1}, target_dir, filename)
        common.write_json({"version": 2}, target_dir, filename)

        with (target_dir / filename).open() as f:
            assert json.load(f) == {"version": 2}
        assert "already exists" in caplog.text

    def test_nested_target_dir_is_created(self, tmp_path):
        target_dir = tmp_path / "a" / "b" / "c"
        common.write_json({}, target_dir, "data.json")
        assert (target_dir / "data.json").exists()

    def test_returns_path_object(self, tmp_path):
        result = common.write_json({}, tmp_path, "data.json")
        assert isinstance(result, type(tmp_path))
