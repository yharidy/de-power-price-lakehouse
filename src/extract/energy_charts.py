"""Extract raw data from the Energy-Charts API and land it as JSON.

Pulls either the `public_power` (generation by production type) or `price`
(day-ahead spot price) endpoint for a given time range and writes the raw,
unmodified API response to a target directory. 

Usage:
    python energy_charts.py --endpoint price --start 2026-01-15 \\
        --end 2026-01-16 --target-path /Volumes/catalog/schema/landing
"""

import json
import logging
from argparse import ArgumentParser
from datetime import UTC, datetime
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

VALID_ENDPOINTS = {"public_power", "price"}
EXPECTED_LICENSE_PREFIX = "CC BY 4.0 (creativecommons.org/licenses/by/4.0)"


class RateLimitError(Exception):
    """Raised when the API responds with HTTP 429.

    Carries the server-supplied `Retry-After` value (in seconds) so the
    retry policy can wait exactly as long as the server asked, instead of
    guessing with a generic backoff.
    """

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


def wait_for_retry(retry_state):
    """Return how long tenacity should wait before the next attempt.

    Honors the server's `Retry-After` header on a `RateLimitError`. For any
    other retried exception (timeouts, connection errors), falls back to
    random exponential backoff so concurrent retries don't collide.
    """
    exception = retry_state.outcome.exception()

    if isinstance(exception, RateLimitError):
        return exception.retry_after

    return wait_random_exponential(multiplier=1, max=30)(retry_state)


def parse_timestamp_string(timestamp_str: str) -> datetime:
    """Parse a Unix timestamp or ISO-8601 string into a UTC datetime.

    Naive ISO strings are assumed to already be UTC. Aware ISO strings are
    converted to UTC. Falls back to interpreting the input as a Unix
    timestamp (seconds since epoch) if ISO parsing fails.

    Raises:
        ValueError: if the string is neither valid ISO-8601 nor a valid
            Unix timestamp.
    """
    try:
        timestamp = datetime.fromisoformat(timestamp_str)

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = timestamp.astimezone(UTC)

        return timestamp

    except ValueError:
        pass

    try:
        return datetime.fromtimestamp(float(timestamp_str), tz=UTC)

    except (ValueError, OverflowError, OSError):
        raise ValueError(
            f"Failed to parse timestamp {timestamp_str}. "
            "Must be a Unix timestamp or an ISO-formatted string."
        )


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


@retry(
    retry=retry_if_exception_type(
        (RateLimitError, requests.Timeout, requests.ConnectionError)
    ),
    wait=wait_for_retry,
    stop=stop_after_attempt(5),
    reraise=True,
)
def fetch(url: str, params: dict, timeout: int = 30) -> dict:
    """GET a URL and return the parsed JSON body.

    Retries up to 5 times on rate limiting (429, honoring `Retry-After`),
    timeouts, and connection errors, with random exponential backoff for
    the latter two. Other HTTP errors (4xx/5xx besides 429) are raised
    immediately via `raise_for_status`.

    Raises:
        RateLimitError: internally, to trigger a retry (not raised to the
            caller unless all attempts are exhausted).
        requests.HTTPError: for non-429 error responses.
    """
    response = requests.get(url, params=params, timeout=timeout)

    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 30))
        logger.warning("Rate limited, waiting %ss", retry_after)
        raise RateLimitError(retry_after)

    response.raise_for_status()

    return response.json()


def main(endpoint: str, start: str, end: str, target_path: str) -> None:
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

    start_dt = parse_timestamp_string(start)
    end_dt = parse_timestamp_string(end)

    url = build_url(endpoint)
    params = build_params(endpoint, start_dt, end_dt)

    response_dict = fetch(url, params)
    check_license_field(response_dict)

    if response_dict.get("deprecated") is True:
        logger.warning("API endpoint %s is deprecated!", url)

    filename = f"{endpoint}_{start_dt.date()}_{end_dt.date()}.json"
    target_file = target_dir / filename

    if target_file.exists():
        logger.warning(
            "Target file already exists: %s. Overwriting...", target_file)

    with target_file.open(mode="w") as f:
        json.dump(response_dict, f)

    logger.info("Wrote %s", target_file)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint", required=True,
        help="API endpoint to call (price or public_power)",
    )
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
        "--target-path", required=True,
        help="Target directory where the response JSON will be written.",
    )

    args = parser.parse_args()
    main(
        endpoint=args.endpoint,
        start=args.start,
        end=args.end,
        target_path=args.target_path,
    )
