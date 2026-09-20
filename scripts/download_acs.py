"""
Download ACS 2020-2024 5-year tract data for Hennepin County from the Census API.

Usage:
    python3 scripts/download_acs.py

Reads:  CENSUS_API_KEY from .env at the repo root (git-ignored)
Writes: data/raw/acs_2024_5yr_hennepin_tracts.json

Variables:
    B19013_001E  median household income (past 12 months, 2024 dollars)
    B25003_002E  owner-occupied housing units
    B25003_003E  renter-occupied housing units

The API response is a list of rows whose first row is the header; it also adds
`state`, `county` and `tract` columns (GEOID = state + county + tract).

The key is never printed: on failure only the HTTP status is shown, not the URL.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
OUT = ROOT / "data" / "raw" / "acs_2024_5yr_hennepin_tracts.json"

BASE = "https://api.census.gov/data/2024/acs/acs5"
VARIABLES = ["B19013_001E", "B25003_002E", "B25003_003E"]


def read_env_key(name):
    """Value of NAME in .env, tolerating spaces around '=' and surrounding quotes."""
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == name:
            return v.strip().strip("'\"")
    return ""


def main():
    key = read_env_key("CENSUS_API_KEY")
    if not key:
        sys.exit("CENSUS_API_KEY is missing or empty in .env")

    query = urllib.parse.urlencode(
        [
            ("get", ",".join(VARIABLES)),
            ("for", "tract:*"),
            ("in", "state:27 county:053"),
            ("key", key),
        ],
        quote_via=urllib.parse.quote,
        safe=":*,",
    )
    try:
        with urllib.request.urlopen(f"{BASE}?{query}", timeout=60) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        sys.exit(f"Census API returned HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach the Census API: {e.reason}")

    try:
        rows = json.loads(body)
        assert isinstance(rows, list) and rows and isinstance(rows[0], list)
    except (ValueError, AssertionError):
        # Not the JSON table we expect (e.g. an "Invalid Key" message); don't echo it.
        sys.exit("Census API response was not a JSON table (is the key valid and activated?)")

    OUT.write_text(body)
    print(f"Wrote {len(rows) - 1} tract rows to {OUT.relative_to(ROOT)}")
    print(f"Header: {rows[0]}")


if __name__ == "__main__":
    main()
