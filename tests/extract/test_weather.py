"""Tests for src/extract/weather.py."""

from unittest.mock import Mock

import pytest

from de_power_price.api import weather


class TestMain:
    def test_writes_expected_filename(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            weather, "fetch", Mock(return_value={"weather": [], "sources": []})
        )

        weather.main(
            lat=52.52,
            lon=13.405,
            start="2026-01-15",
            end="2026-01-16",
            target_path=str(tmp_path),
        )

        expected_file = tmp_path / "weather_2026-01-15_2026-01-16.json"
        assert expected_file.exists()

    def test_calls_fetch_with_brightsky_params(self, tmp_path, monkeypatch):
        fetch_mock = Mock(return_value={"weather": []})
        monkeypatch.setattr(weather, "fetch", fetch_mock)

        weather.main(
            lat=52.52,
            lon=13.405,
            start="2026-01-15T00:00:00",
            end="2026-01-16T00:00:00",
            target_path=str(tmp_path),
        )

        args, kwargs = fetch_mock.call_args
        url, params = args
        assert url == weather.ENDPOINT_URL
        assert params["lat"] == 52.52
        assert params["lon"] == 13.405
        assert "date" in params
        assert "last_date" in params

    def test_same_args_overwrite_same_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(weather, "fetch", Mock(
            return_value={"weather": []}))

        weather.main(52.52, 13.405, "2026-01-15", "2026-01-16", str(tmp_path))
        weather.main(52.52, 13.405, "2026-01-15", "2026-01-16", str(tmp_path))

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

    def test_target_path_as_existing_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(weather, "fetch", Mock(return_value={}))
        existing_file = tmp_path / "not_a_dir"
        existing_file.write_text("oops")

        with pytest.raises(ValueError, match="must be a directory"):
            weather.main(
                52.52, 13.405, "2026-01-15", "2026-01-16", str(existing_file)
            )

    def test_deprecated_flag_logs_warning(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(
            weather, "fetch", Mock(
                return_value={"deprecated": True, "weather": []})
        )

        weather.main(52.52, 13.405, "2026-01-15", "2026-01-16", str(tmp_path))

        assert "deprecated" in caplog.text.lower()
