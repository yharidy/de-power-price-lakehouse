import requests
from datetime import datetime, timezone
from argparse import ArgumentParser
from logging import getLogger
from pathlib import Path
import json
logger = getLogger(__name__)


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
    license = response.get("license_info") or response.get("license")
    if not license.startswith("CC BY 4.0 (creativecommons.org/licenses/by/4.0)"):
        raise RuntimeError(f"Unknown license: {license}")


def main(endpoint: str, start: str, end: str, target_path):
    target_path = Path(target_path)
    if target_path.is_file():
        raise ValueError("Target path must be a directory.")
    target_path.mkdir(exist_ok=True, parents=True)
    start_dt = parse_timestamp_string(start)
    end_dt = parse_timestamp_string(end)
    url = build_url(endpoint)
    params = build_params(endpoint, start_dt, end_dt)
    response = requests.get(url, params)
    response_dict = response.json()
    check_license_field(response_dict)
    if response_dict.get("deprecated") is True:
        logger.warning(f"API endpoint {url} is deprecated!")
    filename = f"{endpoint}_{start_dt.isoformat()}_{end_dt.isoformat()}.json"
    with (target_path / filename).open(mode="w") as f:
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
