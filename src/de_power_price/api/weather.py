"""Extract raw data from the BrightSky Weather API and land it as JSON.

Usage:
    python energy_charts.py --start 2026-01-15 \\
        --end 2026-01-16 --target-path /Volumes/catalog/schema/landing
"""

import logging
from argparse import ArgumentParser
from datetime import UTC, datetime
from pathlib import Path

from .common import fetch, get_previous_day_range, parse_timestamp_string, write_json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ENDPOINT_URL = "https://api.brightsky.dev/weather"


def main(lat: float, lon: float, start: str | datetime, end: str | datetime, target_path: str) -> None:
    """Fetch weather data from the BrightSky API endpoint for a location and time range and write it to disk.

    Raises:
        ValueError: if `target_path` points at an existing file rather
            than a directory.
    """
    target_dir = Path(target_path)
    if target_dir.is_file():
        raise ValueError("Target path must be a directory.")
    target_dir.mkdir(exist_ok=True, parents=True)

    if isinstance(start, str):
        start: datetime = parse_timestamp_string(start)
    if isinstance(end, str):
        end: datetime = parse_timestamp_string(end)

    if start.tzinfo != UTC or end.tzinfo != UTC:
        raise ValueError("Start/end timestamps are not in UTC.")

    params = {"lat": lat, "lon": lon, "date": start.isoformat(),
              "last_date": end.isoformat()}

    response_dict = fetch(ENDPOINT_URL, params)

    if response_dict.get("deprecated") is True:
        logger.warning("API endpoint %s is deprecated!", ENDPOINT_URL)

    filename = f"weather_{start.date()}_{end.date()}.json"
    write_json(response_dict, target_dir, filename)


def cli():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--previous-day",
        action='store_true',
        help=(
            "Set start time to the previous day at 00:00, end at 23:59."
            "Overwrites values passed to --start and --end"
        ),
    )
    parser.add_argument(
        "--start",
        help=(
            "Start time to request in UTC (unix timestamp or ISO-format "
            "date-time string, e.g. 2026-02-12T10:52:59Z)"
        ),
    )
    parser.add_argument(
        "--end",
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

    if not args.previous_day and not (args.start and args.end):
        raise ValueError(
            "--previous-day must be set or a start and end timestmaps must be provided")
    if args.previous_day:
        start, end = get_previous_day_range()
        logger.info(
            f"Resolved timestamp pounds for previous day: start={start.isoformat()}, end={end.isoformat()} ")
    else:
        start, end = args.start, args.end
    main(
        start=start,
        end=end,
        lon=args.lon,
        lat=args.lat,
        target_path=args.target_path,
    )


if __name__ == "__main__":
    cli()
