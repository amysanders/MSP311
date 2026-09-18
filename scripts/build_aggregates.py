"""
Turns the raw 311 CSV into small JSON summaries the frontend can load directly,
instead of parsing ~250k rows of CSV in the browser.

Usage:
    python3 scripts/build_aggregates.py

Reads:  data/raw/minneapolis_311_2024_2026Q2.csv
        data/raw/neighborhoods.geojson
Writes: data/processed/by_type.json
        data/processed/overall.json
        data/processed/by_neighborhood.json
        data/processed/neighborhoods.geojson   (slimmed boundaries for the map)

Cases with no usable location (LON/LAT of 0.0) are labeled UNKNOWN_LOCATION
rather than dropped or plotted at (0, 0). They get their own row in
by_neighborhood.json instead of being joined to a neighborhood.

Located cases are joined to a neighborhood with a point-in-polygon test. Cases
with real coordinates that fall inside no neighborhood polygon are reported
separately as OUTSIDE_NEIGHBORHOODS.
"""

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "minneapolis_311_2024_2026Q2.csv"
NEIGHBORHOODS_GEOJSON = ROOT / "data" / "raw" / "neighborhoods.geojson"
OUT_DIR = ROOT / "data" / "processed"

UNKNOWN_LOCATION = "Unknown location"
OUTSIDE_NEIGHBORHOODS = "Outside neighborhoods"


def load_rows():
    with open(RAW_CSV, newline="") as f:
        reader = csv.DictReader(f)
        yield from reader


def has_location(row):
    """False for cases exported with placeholder 0.0 coordinates (~20% of rows)."""
    return float(row["LON"]) != 0 and float(row["LAT"]) != 0


def location_of(row):
    """(lon, lat) for a located case, or UNKNOWN_LOCATION."""
    if not has_location(row):
        return UNKNOWN_LOCATION
    return float(row["LON"]), float(row["LAT"])


def percentile(sorted_values, p):
    idx = min(int(len(sorted_values) * p), len(sorted_values) - 1)
    return round(sorted_values[idx], 1)


def load_neighborhoods():
    """Neighborhood polygons as dicts of name, id, rings (outer first, then holes), bbox."""
    with open(NEIGHBORHOODS_GEOJSON) as f:
        features = json.load(f)["features"]
    neighborhoods = []
    for feat in features:
        assert feat["geometry"]["type"] == "Polygon", feat["properties"]["BDNAME"]
        rings = feat["geometry"]["coordinates"]
        xs = [x for x, _ in rings[0]]
        ys = [y for _, y in rings[0]]
        neighborhoods.append(
            {
                "name": feat["properties"]["BDNAME"],
                "id": feat["properties"]["BDNUM"],
                "rings": rings,
                "bbox": (min(xs), min(ys), max(xs), max(ys)),
            }
        )
    return neighborhoods


def point_in_ring(x, y, ring):
    """Ray casting: count how many ring edges a rightward ray from (x, y) crosses."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def find_neighborhood(lon, lat, neighborhoods):
    """Name of the neighborhood containing (lon, lat), or OUTSIDE_NEIGHBORHOODS."""
    for n in neighborhoods:
        min_x, min_y, max_x, max_y = n["bbox"]
        if not (min_x <= lon <= max_x and min_y <= lat <= max_y):
            continue
        outer, *holes = n["rings"]
        if point_in_ring(lon, lat, outer) and not any(
            point_in_ring(lon, lat, h) for h in holes
        ):
            return n["name"]
    return OUTSIDE_NEIGHBORHOODS


def build_by_neighborhood():
    """Resolution stats per neighborhood, plus unknown-location and outside-city rows."""
    neighborhoods = load_neighborhoods()
    names = [n["name"] for n in neighborhoods]
    hours = {name: [] for name in names + [UNKNOWN_LOCATION, OUTSIDE_NEIGHBORHOODS]}
    n_open = dict.fromkeys(hours, 0)
    cache = {}  # many cases share the exact same geocoded point

    for row in load_rows():
        loc = location_of(row)
        if loc == UNKNOWN_LOCATION:
            key = UNKNOWN_LOCATION
        else:
            if loc not in cache:
                cache[loc] = find_neighborhood(*loc, neighborhoods)
            key = cache[loc]
        rh = row["resolution_hours"]
        if rh:
            hours[key].append(float(rh))
        else:
            n_open[key] += 1

    def summarize(name):
        h = sorted(hours[name])
        stats = {
            "n_cases": len(h) + n_open[name],
            "n_closed": len(h),
            "n_open": n_open[name],
            "median_hours": None,
            "mean_hours": None,
            "p90_hours": None,
        }
        if h:
            stats["median_hours"] = round(statistics.median(h), 1)
            stats["mean_hours"] = round(statistics.mean(h), 1)
            stats["p90_hours"] = percentile(h, 0.90)
        return stats

    return {
        "neighborhoods": [{"neighborhood": n, **summarize(n)} for n in names],
        UNKNOWN_LOCATION: summarize(UNKNOWN_LOCATION),
        OUTSIDE_NEIGHBORHOODS: summarize(OUTSIDE_NEIGHBORHOODS),
    }


def build_neighborhood_geojson():
    """Boundaries slimmed for the browser: name/id only, coordinates rounded to ~1 m."""
    features = []
    for n in load_neighborhoods():
        rings = []
        for ring in n["rings"]:
            pts = []
            for x, y in ring:
                p = [round(x, 5), round(y, 5)]
                if not pts or p != pts[-1]:
                    pts.append(p)
            rings.append(pts)
        features.append(
            {
                "type": "Feature",
                "properties": {"name": n["name"], "id": n["id"]},
                "geometry": {"type": "Polygon", "coordinates": rings},
            }
        )
    return {"type": "FeatureCollection", "features": features}


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
    n_unknown_location = 0
    for row in load_rows():
        n_total += 1
        if location_of(row) == UNKNOWN_LOCATION:
            n_unknown_location += 1
        rh = row["resolution_hours"]
        if rh:
            all_hours.append(float(rh))
        else:
            n_open += 1

    all_hours.sort()
    n = len(all_hours)

    return {
        "n_total_cases": n_total,
        "n_closed": n,
        "n_open": n_open,
        "n_unknown_location": n_unknown_location,
        "median_hours": round(statistics.median(all_hours), 1),
        "mean_hours": round(statistics.mean(all_hours), 1),
        "p75_hours": percentile(all_hours, 0.75),
        "p90_hours": percentile(all_hours, 0.90),
        "p95_hours": percentile(all_hours, 0.95),
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

    by_neighborhood = build_by_neighborhood()
    (OUT_DIR / "by_neighborhood.json").write_text(json.dumps(by_neighborhood, indent=2))
    print(
        f"Wrote {len(by_neighborhood['neighborhoods'])} neighborhoods to "
        "data/processed/by_neighborhood.json"
    )
    for label in (UNKNOWN_LOCATION, OUTSIDE_NEIGHBORHOODS):
        print(f"  {label}: {by_neighborhood[label]['n_cases']} cases")

    (OUT_DIR / "neighborhoods.geojson").write_text(
        json.dumps(build_neighborhood_geojson(), separators=(",", ":"))
    )
    print("Wrote slimmed boundaries to data/processed/neighborhoods.geojson")


if __name__ == "__main__":
    main()
