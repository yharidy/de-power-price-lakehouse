"""Tests for src/extract/energy_charts.py."""

from datetime import UTC, datetime
from unittest.mock import Mock

from de_power_price.api import energy_charts
import pytest

# ---------------------------------------------------------------------------
# build_url
# ---------------------------------------------------------------------------


class TestBuildUrl:
    @pytest.mark.parametrize(
        "endpoint,expected",
        [
            ("public_power", "https://api.energy-charts.info/v2/public_power"),
            ("price", "https://api.energy-charts.info/v2/price"),
        ],
    )
    def test_valid_endpoints(self, endpoint, expected):
        assert energy_charts.build_url(endpoint) == expected

    def test_invalid_endpoint_raises(self):
        with pytest.raises(ValueError, match="Unrecognized endpoint"):
            energy_charts.build_url("not_a_real_endpoint")


# ---------------------------------------------------------------------------
# build_params
# ---------------------------------------------------------------------------

class TestBuildParams:
    def setup_method(self):
        self.start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        self.end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)

    def test_public_power_scoped_by_country(self):
        params = energy_charts.build_params(
            "public_power", self.start, self.end)
        assert params["country"] == "de"
        assert "bzn" not in params
        assert params["start"] == self.start.isoformat()
        assert params["end"] == self.end.isoformat()

    def test_price_scoped_by_bidding_zone(self):
        params = energy_charts.build_params("price", self.start, self.end)
        assert params["bzn"] == "DE-LU"
        assert "country" not in params

    def test_invalid_endpoint_raises(self):
        with pytest.raises(ValueError, match="Unrecognized endpoint"):
            energy_charts.build_params("bogus", self.start, self.end)


# ---------------------------------------------------------------------------
# check_license_field
# ---------------------------------------------------------------------------

class TestCheckLicenseField:
    def test_expected_license_passes(self):
        response = {
            "license_info": "CC BY 4.0 (creativecommons.org/licenses/by/4.0)"
        }
        energy_charts.check_license_field(response)  # should not raise

    def test_expected_license_under_license_key_passes(self):
        response = {
            "license": "CC BY 4.0 (creativecommons.org/licenses/by/4.0)"}
        energy_charts.check_license_field(response)  # should not raise

    def test_unexpected_license_raises(self):
        response = {"license_info": "All Rights Reserved"}
        with pytest.raises(RuntimeError, match="Unknown license"):
            energy_charts.check_license_field(response)

    def test_missing_license_field_does_not_raise(self):
        response = {"unix_seconds": [], "production_types": []}
        energy_charts.check_license_field(response)  # should not raise

    def test_none_license_value_does_not_raise(self):
        response = {"license_info": None}
        energy_charts.check_license_field(response)  # should not raise

    def test_empty_string_license_does_not_raise(self):
        # Falsy value should be treated the same as "missing".
        response = {"license_info": ""}
        energy_charts.check_license_field(response)  # should not raise


# ---------------------------------------------------------------------------
# main (integration of the pieces above, with fetch/write_json mocked)
# ---------------------------------------------------------------------------

class TestMain:
    def test_writes_expected_filename_and_content(self, tmp_path, monkeypatch):
        fake_response = {
            "license_info": "CC BY 4.0 (creativecommons.org/licenses/by/4.0)",
            "unix_seconds": [1, 2, 3],
        }
        monkeypatch.setattr(
            energy_charts, "fetch", Mock(return_value=fake_response)
        )

        energy_charts.main(
            endpoint="price",
            start="2026-01-15",
            end="2026-01-16",
            target_path=str(tmp_path),
        )

        expected_file = tmp_path / "price_2026-01-15_2026-01-16.json"
        assert expected_file.exists()

    def test_same_args_overwrite_same_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            energy_charts, "fetch", Mock(return_value={"unix_seconds": [1]})
        )

        energy_charts.main("price", "2026-01-15", "2026-01-16", str(tmp_path))
        energy_charts.main("price", "2026-01-15", "2026-01-16", str(tmp_path))

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

    def test_target_path_as_existing_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(energy_charts, "fetch", Mock(return_value={}))
        existing_file = tmp_path / "not_a_dir"
        existing_file.write_text("oops")

        with pytest.raises(ValueError, match="must be a directory"):
            energy_charts.main(
                "price", "2026-01-15", "2026-01-16", str(existing_file)
            )

    def test_unexpected_license_propagates_and_blocks_write(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            energy_charts,
            "fetch",
            Mock(return_value={"license_info": "All Rights Reserved"}),
        )

        with pytest.raises(RuntimeError, match="Unknown license"):
            energy_charts.main(
                "price", "2026-01-15", "2026-01-16", str(tmp_path)
            )

        assert list(tmp_path.glob("*.json")) == []

    def test_deprecated_endpoint_logs_warning_but_still_writes(
        self, tmp_path, monkeypatch, caplog
    ):
        monkeypatch.setattr(
            energy_charts,
            "fetch",
            Mock(return_value={"deprecated": True, "unix_seconds": []}),
        )

        energy_charts.main("price", "2026-01-15", "2026-01-16", str(tmp_path))

        assert "deprecated" in caplog.text.lower()
        assert list(tmp_path.glob("*.json"))
