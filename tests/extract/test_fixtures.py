"""Tests that exercise write_json / check_license_field against real,
saved API responses, in place of hand-typed fixtures.
"""

import json
from pathlib import Path

import common
import energy_charts
import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> dict:
    with (FIXTURES_DIR / name).open() as f:
        return json.load(f)


@pytest.fixture
def price_sample():
    return _load("price_sample.json")


@pytest.fixture
def public_power_sample():
    return _load("public_power_sample.json")


@pytest.fixture
def weather_sample():
    return _load("weather_sample.json")


class TestCheckLicenseFieldAgainstRealSamples:
    """Real responses use 'license', not 'license_info' -- confirms our
    function's key-fallback logic actually matches what the API sends,
    rather than only the key we guessed when we wrote the function."""

    def test_price_sample(self, price_sample):
        energy_charts.check_license_field(price_sample)  # should not raise

    def test_public_power_sample(self, public_power_sample):
        energy_charts.check_license_field(
            public_power_sample)  # should not raise


class TestWriteJsonRoundTrip:
    """Confirms write_json doesn't mangle real, complex payloads --
    nested dicts, negative floats, nulls -- on the way to disk and back."""

    @pytest.mark.parametrize(
        "fixture_name",
        ["price_sample.json", "public_power_sample.json", "weather_sample.json"],
    )
    def test_round_trip_preserves_content(self, tmp_path, fixture_name):
        original = _load(fixture_name)
        written_path = common.write_json(original, tmp_path, "out.json")
        with written_path.open() as f:
            reloaded = json.load(f)
        assert reloaded == original

    def test_negative_prices_survive_round_trip(self, tmp_path, price_sample):
        written_path = common.write_json(price_sample, tmp_path, "out.json")
        with written_path.open() as f:
            reloaded = json.load(f)
        original_prices = [r["values"]["day_ahead_price"]
                           for r in price_sample["data"]]
        reloaded_prices = [r["values"]["day_ahead_price"]
                           for r in reloaded["data"]]
        assert reloaded_prices == original_prices
