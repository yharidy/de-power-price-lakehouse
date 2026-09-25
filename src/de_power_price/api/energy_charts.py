"""Extract raw data from the Energy-Charts API and land it as JSON.

Pulls either the `public_power` (generation by production type) or `price`
(day-ahead spot price) endpoint for a given time range and writes the raw,
unmodified API response to a target directory. 

Usage:
    python energy_charts.py --endpoint price --start 2026-01-15 \\
        --end 2026-01-16 --target-path /Volumes/catalog/schema/landing
"""

import logging
from argparse import ArgumentParser
from datetime import UTC, datetime
from pathlib import Path

from .common import (
    fetch,
    get_previous_day_range,
    parse_timestamp_string,
    write_json,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

VALID_ENDPOINTS = {"public_power", "price"}
EXPECTED_LICENSE_PREFIX = "CC BY 4.0 (creativecommons.org/licenses/by/4.0)"


def build_url(endpoint: str) -> str:
    """Build the full URL for a supported Energy-Charts v2 endpoint.

    Raises:
        ValueError: if `endpoint` is not one of VALID_ENDPOINTS.
    """
    if endpoint not in VALID_ENDPOINTS:
        raise ValueError(
            f"Unrecognized endpoint: {endpoint}. "
            f"Accepted endpoints are {sorted(VALID_ENDPOINTS)}."
        )
    base_url = "https://api.energy-charts.info/v2"
    return f"{base_url}/{endpoint}"


def build_params(endpoint: str, start: datetime, end: datetime) -> dict:
    """Build the query parameters for a given endpoint and time range.

    `public_power` is scoped by country ("de"); `price` is scoped by
    bidding zone ("DE-LU"), since day-ahead prices are set per zone rather
    than per country.

    Raises:
        ValueError: if `endpoint` is not one of VALID_ENDPOINTS.
    """
    if endpoint not in VALID_ENDPOINTS:
        raise ValueError(
            f"Unrecognized endpoint: {endpoint}. "
            f"Accepted endpoints are {sorted(VALID_ENDPOINTS)}."
        )
    params = {"start": start.isoformat(), "end": end.isoformat()}
    if endpoint == "public_power":
        params["country"] = "de"
    else:
        params["bzn"] = "DE-LU"  # bidding zone
    return params


def check_license_field(response: dict) -> None:
    """Verify the response's declared license matches what we expect.

    The API may omit a license field entirely (nothing to check in that
    case), but if one is present and it doesn't match CC BY 4.0, raise so
    a silent license change doesn't go unnoticed.

    Raises:
        RuntimeError: if a license field is present and unexpected.
    """
    license_info = response.get("license_info") or response.get("license")
    if license_info and not license_info.startswith(EXPECTED_LICENSE_PREFIX):
        raise RuntimeError(f"Unknown license: {license_info}")


def main(endpoint: str, start: str | datetime, end: str | datetime, target_path: str) -> None:
    """Fetch one Energy-Charts endpoint for a time range and write it to disk.

    The output filename is derived from the requested start/end *dates*
    , so re-running with the same arguments overwrites the same file. 
    This keeps ingestion idempotent regardless
    of what the API happens to return on a given call.

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

    url = build_url(endpoint)
    params = build_params(endpoint, start, end)

    response_dict = fetch(url, params)
    check_license_field(response_dict)

    if response_dict.get("deprecated") is True:
        logger.warning("API endpoint %s is deprecated!", url)

    filename = f"{endpoint}_{start.date()}_{end.date()}.json"
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
        "--endpoint", required=True,
        help="API endpoint to call (price or public_power)",
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
        endpoint=args.endpoint,
        start=start,
        end=end,
        target_path=args.target_path,
    )


if __name__ == "__main__":
    cli()
