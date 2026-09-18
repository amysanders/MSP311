# Minneapolis 311: How fast does the city resolve requests?

As a Minneapolis resident, I wanted to understand how quickly the city
resolves 311 service requests — and whether that varies by request type
and by location.

## Data

Source: [City of Minneapolis Open Data Portal](https://opendata.minneapolismn.gov/),
Public 311 case exports for 2024, 2025, and 2026 (GeoJSON).

- Merged the three yearly exports, normalizing two different date formats
  (ISO 8601 vs. RFC 822) found across files.
- Deduped ~1,184 cases that appeared in both the 2024 and 2025 exports
  (cases opened in late 2024, re-exported once updated).
- Computed `resolution_hours` = Closed Date Time − Opened Date Time for
  every closed case.
- **Cutoff: cases opened January 2024 – June 2026 only.** Cases from
  July–September 2026 were excluded because they hadn't had enough time
  to close yet — including them would make recent months look
  artificially fast. At the June 2026 cutoff, only 0.81% of remaining
  cases are still open.

- **Unknown locations:** 49,516 cases (~20%) have `LON`/`LAT` of exactly
  `0.0` in the export. These are treated as **"Unknown location"** — kept in
  all overall and by-type stats, but never plotted or joined to a
  neighborhood. The CSV is left as exported; the labeling happens in
  `scripts/build_aggregates.py`.
- **Neighborhoods:** boundaries for the 87 official Minneapolis neighborhoods
  come from the City's
  [Minneapolis Neighborhoods](https://opendata.minneapolismn.gov/datasets/cityoflakes::minneapolis-neighborhoods/about)
  dataset (CC0), downloaded as GeoJSON in lat/lon from its ArcGIS
  FeatureServer (layer 0, downloaded 2026-09-18) to
  `data/raw/neighborhoods.geojson`. Each located case is assigned to a
  neighborhood with a point-in-polygon test in `build_aggregates.py`. Another
  469 cases (0.19%) have real coordinates that fall inside no neighborhood
  polygon; they're reported as "Outside neighborhoods" and not mapped.

See `data/raw/minneapolis_311_2024_2026Q2.csv` for the cleaned dataset.
Columns: `CASEID, TYPENAME, SUBJECTNAME, REASONNAME, CASESTATUS,
OPENEDDATETIME, CLOSEDDATETIME, LON, LAT, resolution_hours`.

## Structure

```
data/
  raw/            cleaned, cutoff-filtered CSV (source of truth) and the
                  neighborhood boundary GeoJSON
  processed/      small JSON/GeoJSON files the frontend actually loads
scripts/
  build_aggregates.py   raw data -> data/processed/*
web/
  index.html, style.css, app.js   the visualization itself (Chart.js + Leaflet)
```

## Running it

```bash
# 1. Regenerate the aggregates (only needed if data/raw changes)
python3 scripts/build_aggregates.py

# 2. Serve the repo root (fetch() needs http://, not file://, and the page
#    loads ../data/processed/*.json, so data/ must be inside the served folder)
python3 -m http.server 8000
# then open http://localhost:8000/web/
```

## Findings so far

- Median resolution time across all request types: **22.3 hours** (~0.9 days).
- Mean is much higher (111.7 hours) — a long tail of slow-to-resolve
  categories (e.g. abandoned vehicles, property complaints) pulls the
  average up. **Median is the more honest headline number.**
- There's a recurring seasonal slowdown each November/December
  (still-open rate for cases opened that month runs noticeably higher
  than the rest of the year) — worth investigating further.
- By neighborhood, most medians are tightly bunched: the middle 60% of the
  87 neighborhoods fall between about 20 and 25 hours. The extremes are
  fastest **Near - North (3.2 h)** and slowest **Central (42.9 h)**.
- **Neighborhood medians partly reflect request-type mix, not just
  responsiveness.** 63% of Near - North's closed cases are "Animal Complaint -
  Livability", a type that closes in about 2 hours city-wide; within that
  neighborhood, per-type medians look like the city's. The map page says this
  too.
- Cases with no location (20%) have a median of 23.9 h, close to the overall
  22.3 h, but a heavier tail (mean 141.6 h vs 111.7 h; 90th percentile
  294.6 h vs 220.0 h). The map's medians aren't much affected by leaving them
  out, but they aren't a random sample of slow cases either.

## Still to do

- [x] Join case LON/LAT to Minneapolis neighborhood boundaries
- [x] Build the by-neighborhood aggregate + map view
- [ ] Write up the November/December seasonal pattern
- [ ] Control for request-type mix on the neighborhood map (e.g. compare each
      neighborhood's per-type medians to the city-wide medians)
- [ ] Look into why Near - North has so many animal complaints (5,432) —
      possibly cases geocoded to a single address
- [ ] Shorten or wrap long request-type labels on the by-type chart at phone
      widths
