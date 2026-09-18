"""
Turns the raw 311 CSV into small JSON summaries the frontend can load directly,
instead of parsing ~250k rows of CSV in the browser.

Usage:
    python3 scripts/build_aggregates.py

Reads:  data/raw/minneapolis_311_2024_2026Q2.csv
Writes: data/processed/by_type.json
        data/processed/overall.json

TODO (next step): once neighborhood boundary polygons are added, join each
case's LON/LAT to a neighborhood and write data/processed/by_neighborhood.json
using the same median-based approach as by_type.json.
"""

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "minneapolis_311_2024_2026Q2.csv"
OUT_DIR = ROOT / "data" / "processed"


def load_rows():
    with open(RAW_CSV, newline="") as f:
        reader = csv.DictReader(f)
        yield from reader


def build_by_type():
    """Median/mean/count resolution stats per request type, closed cases only."""
    by_type = {}
    for row in load_rows():
        rh = row["resolution_hours"]
        if not rh:
            continue  # still-open case, skip
        t = row["TYPENAME"] or "Unknown"
        by_type.setdefault(t, []).append(float(rh))

    result = []
    for t, hours in by_type.items():
        result.append(
            {
                "type": t,
                "n": len(hours),
                "median_hours": round(statistics.median(hours), 1),
                "mean_hours": round(statistics.mean(hours), 1),
            }
        )
    # Sort slowest-to-resolve first; easy to reverse in the frontend if needed
    result.sort(key=lambda r: r["median_hours"], reverse=True)
    return result


def build_overall():
    all_hours = []
    n_open = 0
    n_total = 0
    for row in load_rows():
        n_total += 1
        rh = row["resolution_hours"]
        if rh:
            all_hours.append(float(rh))
        else:
            n_open += 1

    all_hours.sort()
    n = len(all_hours)

    def pct(p):
        idx = min(int(n * p), n - 1)
        return round(all_hours[idx], 1)

    return {
        "n_total_cases": n_total,
        "n_closed": n,
        "n_open": n_open,
        "median_hours": round(statistics.median(all_hours), 1),
        "mean_hours": round(statistics.mean(all_hours), 1),
        "p75_hours": pct(0.75),
        "p90_hours": pct(0.90),
        "p95_hours": pct(0.95),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    by_type = build_by_type()
    (OUT_DIR / "by_type.json").write_text(json.dumps(by_type, indent=2))
    print(f"Wrote {len(by_type)} request types to data/processed/by_type.json")

    overall = build_overall()
    (OUT_DIR / "overall.json").write_text(json.dumps(overall, indent=2))
    print(f"Wrote overall stats to data/processed/overall.json")
    print(overall)


if __name__ == "__main__":
    main()
