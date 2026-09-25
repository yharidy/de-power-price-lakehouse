import requests
from datetime import datetime, timezone
from argparse import ArgumentParser
import logging
from pathlib import Path
import json
from tenacity import retry, wait_random_exponential, retry_if_exception_type, stop_after_attempt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class RateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


def wait_for_retry(retry_state):
    exception = retry_state.outcome.exception()

    if isinstance(exception, RateLimitError):
        return exception.retry_after

    return wait_random_exponential(
        multiplier=1,
        max=30,
    )(retry_state)


def parse_timestamp_string(timestamp_str: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(timestamp_str)

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

        return timestamp

    except ValueError:
        pass

    try:
        return datetime.fromtimestamp(float(timestamp_str), tz=timezone.utc)

    except (ValueError, OverflowError, OSError):
        raise ValueError(
            f"Failed to parse timestamp {timestamp_str}. "
            "Must be a Unix timestamp or an ISO-formatted string."
        )


def build_url(endpoint: str):
    if endpoint not in {"public_power", "price"}:
        raise ValueError(
            f"Unrecognized endpoint: {endpoint}. Accepted endpoints are public_power or price.")
    base_url = "https://api.energy-charts.info/v2"
    return f"{base_url}/{endpoint}"


def build_params(endpoint: str, start: datetime, end: datetime):
    if endpoint not in {"public_power", "price"}:
        raise ValueError(
            f"Unrecognized endpoint: {endpoint}. Accepted endpoints are public_power or price.")
    params = {"start": start.isoformat(), "end": end.isoformat()}
    if endpoint == "public_power":
        params["country"] = "de"
    else:
        params["bzn"] = "DE-LU"  # bidding zone
    return params


def check_license_field(response: dict):
    license_info = response.get("license_info") or response.get("license")
    if license_info and not license_info.startswith("CC BY 4.0 (creativecommons.org/licenses/by/4.0)"):
        raise RuntimeError(f"Unknown license: {license_info}")


@retry(
    retry=retry_if_exception_type(
        (
            RateLimitError,
            requests.Timeout,
            requests.ConnectionError,
        )
    ),
    wait=wait_for_retry,
    stop=stop_after_attempt(5),
    reraise=True,
)
def fetch(url, params, timeout: int = 30) -> dict:
    response = requests.get(
        url,
        params=params,
        timeout=timeout,
    )

    if response.status_code == 429:
        retry_after = int(
            response.headers.get("Retry-After", 30)
        )
        logger.warning(
            "Rate limited, waiting %ss",
            retry_after,
        )
        raise RateLimitError(retry_after)

    response.raise_for_status()

    return response.json()


def main(endpoint: str, start: str, end: str, target_path):
    target_path = Path(target_path)
    if target_path.is_file():
        raise ValueError("Target path must be a directory.")
    target_path.mkdir(exist_ok=True, parents=True)
    start_dt = parse_timestamp_string(start)
    end_dt = parse_timestamp_string(end)
    url = build_url(endpoint)
    params = build_params(endpoint, start_dt, end_dt)
    response_dict = fetch(url, params)
    check_license_field(response_dict)
    if response_dict.get("deprecated") is True:
        logger.warning(f"API endpoint {url} is deprecated!")
    filename = f"{endpoint}_{start_dt.date()}_{end_dt.date()}.json"
    target_file = target_path / filename
    if target_file.exists():
        logger.warning("Target file already exists! Overwriting...")
    with target_file.open(mode="w") as f:
        json.dump(response_dict, f)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--endpoint", required=True,
                        help="API endpoint to call (price or public_power)")
    parser.add_argument("--start", required=True,
                        help="Start time to request in UTC (unix timestamp or iso-format date-time string e.g. 2026-02-12T10:52:59Z)")
    parser.add_argument("--end", required=True,
                        help="End time to request in UTC (unix timestamp or iso-format date-time string e.g. 2026-02-12T10:52:59Z)")
    parser.add_argument("--target-path", required=True,
                        help="Target path where to dump the response JSONs.")

    args = parser.parse_args()
    main(endpoint=args.endpoint, start=args.start,
         end=args.end, target_path=args.target_path)
