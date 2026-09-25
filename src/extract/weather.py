"""Extract raw data from the BrightSky Weather API and land it as JSON.

Usage:
    python energy_charts.py --start 2026-01-15 \\
        --end 2026-01-16 --target-path /Volumes/catalog/schema/landing
"""

import json
import logging
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

from common import fetch, parse_timestamp_string, write_json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ENDPOINT_URL = "https://api.brightsky.dev/weather"


def main(lat: float, lon: float, start: str, end: str, target_path: str) -> None:
    """Fetch weather data from the BrightSky API endpoint for a location and time range and write it to disk.

    Raises:
        ValueError: if `target_path` points at an existing file rather
            than a directory.
    """
    target_dir = Path(target_path)
    if target_dir.is_file():
        raise ValueError("Target path must be a directory.")
    target_dir.mkdir(exist_ok=True, parents=True)

    start_dt: datetime = parse_timestamp_string(start)
    end_dt: datetime = parse_timestamp_string(end)

    params = {"lat": lat, "lon": lon, "date": start_dt.isoformat(),
              "last_date": end_dt.isoformat()}

    response_dict = fetch(ENDPOINT_URL, params)

    if response_dict.get("deprecated") is True:
        logger.warning("API endpoint %s is deprecated!", ENDPOINT_URL)

    filename = f"weather_{start_dt.date()}_{end_dt.date()}.json"
    write_json(response_dict, target_dir, filename)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start", required=True,
        help=(
            "Start time to request in UTC (unix timestamp or ISO-format "
            "date-time string, e.g. 2026-02-12T10:52:59Z)"
        ),
    )
    parser.add_argument(
        "--end", required=True,
        help=(
            "End time to request in UTC (unix timestamp or ISO-format "
            "date-time string, e.g. 2026-02-12T10:52:59Z)"
        ),
    )
    parser.add_argument(
        "--lat", default=52.52,
        help=(
            "Latitude coordinate."
        ),
    )
    parser.add_argument(
        "--lon", default=13.405,
        help=(
            "Longitude coordinate."
        ),
    )
    parser.add_argument(
        "--target-path", required=True,
        help="Target directory where the response JSON will be written.",
    )

    args = parser.parse_args()
    main(
        start=args.start,
        end=args.end,
        lon=args.lon,
        lat=args.lat,
        target_path=args.target_path,
    )
