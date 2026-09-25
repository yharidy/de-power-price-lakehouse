"""Shared HTTP fetch, retry, and file-write helpers for API extraction scripts."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when the API responds with HTTP 429."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


def wait_for_retry(retry_state):
    exception = retry_state.outcome.exception()
    if isinstance(exception, RateLimitError):
        return exception.retry_after
    return wait_random_exponential(multiplier=1, max=30)(retry_state)


def get_previous_day_range() -> tuple[datetime, datetime]:
    today = datetime.now(UTC).date()
    previous_day = today - timedelta(days=1)

    start = datetime.combine(
        previous_day,
        datetime.min.time(),
        tzinfo=UTC,
    )

    end = start + timedelta(days=1)

    return start, end


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


@retry(
    retry=retry_if_exception_type(
        (RateLimitError, requests.Timeout, requests.ConnectionError)),
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


def write_json(payload: dict, target_dir: Path, filename: str) -> Path:
    """Write payload to target_dir/filename, overwriting if present, and
    return the path written.
    """
    target_dir.mkdir(exist_ok=True, parents=True)
    target_file = target_dir / filename
    if target_file.exists():
        logger.warning(
            "Target file already exists: %s. Overwriting...", target_file)
    with target_file.open(mode="w") as f:
        json.dump(payload, f)
    logger.info("Wrote %s", target_file)
    return target_file
