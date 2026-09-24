# Minneapolis 311: How fast does the city resolve requests?

As a Minneapolis resident, I wanted to understand how quickly the city
resolves 311 service requests — and whether that varies by request type
and by location.

## Data

Source: [City of Minneapolis Open Data Portal](https://opendata.minneapolismn.gov/),
public 311 case data. The working file, `minneapolis_311_2023_2026_3yr.csv`,
covers **36 months of cases: opened July 2023 – June 2026** (292,722 cases). It
extends the earlier January 2024 – June 2026 extract by six months; for the
245,704 cases in the overlap, every column is identical to that earlier file.

Cleaning applied to the 2024 – June 2026 exports:

- Merged the three yearly exports, normalizing two different date formats
  (ISO 8601 vs. RFC 822) found across files.
- Deduped ~1,184 cases that appeared in both the 2024 and 2025 exports
  (cases opened in late 2024, re-exported once updated).
- Computed `resolution_hours` = Closed Date Time − Opened Date Time for
  every closed case.

The July–December 2023 cases (47,018) were added on 2026-09-20. I checked that
they have the same columns and ISO timestamps, no duplicate case IDs, and no
negative resolution times; I did not re-derive how they were cleaned.

- **Cutoff: cases opened July 2023 – June 2026 only.** Cases from
  July–September 2026 were excluded because they hadn't had enough time
  to close yet — including them would make recent months look
  artificially fast. At the June 2026 cutoff, only 0.75% of remaining
  cases are still open.
- **Unknown locations:** 58,769 cases (~20%) have `LON`/`LAT` of exactly
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
  569 cases (0.19%) have real coordinates that fall inside no neighborhood
  polygon; they're reported as "Outside neighborhoods" and not mapped.

See `data/raw/minneapolis_311_2023_2026_3yr.csv` for the cleaned dataset.
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
  index.html, style.css, app.js   the visualization itself (Leaflet map)
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

- By neighborhood, most medians are tightly bunched: the middle 60% of the
  87 neighborhoods fall between about 20 and 25 hours. The extremes are
  fastest **Near - North (3.5 h)** and slowest **Nicollet Island - East Bank
  (46.5 h)**.
- **Neighborhood medians partly reflect request-type mix, not just
  responsiveness.** 62% of Near - North's closed cases are "Animal Complaint -
  Livability", a type that closes in about 2 hours city-wide; within that
  neighborhood, per-type medians look like the city's. The map page says this
  too.
- Cases with no location (20%) have a median of 24.0 h, close to the overall
  22.8 h, but a heavier tail (mean 142.6 h vs 117.4 h; 90th percentile
  306.2 h vs 236.3 h). The map's medians aren't much affected by leaving them
  out, but they aren't a random sample of slow cases either.

## Still to do

- [x] Join case LON/LAT to Minneapolis neighborhood boundaries
- [x] Build the by-neighborhood aggregate + map view
- [ ] Control for request-type mix on the neighborhood map (e.g. compare each
      neighborhood's per-type medians to the city-wide medians)
- [ ] Look into why Near - North has so many animal complaints (6,142) —
      possibly cases geocoded to a single address
- [ ] Design and build a request-type picker (chips for top subjects/types +
      search + browse) so the map can be filtered by request type
