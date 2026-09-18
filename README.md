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

See `data/raw/minneapolis_311_2024_2026Q2.csv` for the cleaned dataset.
Columns: `CASEID, TYPENAME, SUBJECTNAME, REASONNAME, CASESTATUS,
OPENEDDATETIME, CLOSEDDATETIME, LON, LAT, resolution_hours`.

## Structure

```
data/
  raw/            cleaned, cutoff-filtered CSV (source of truth)
  processed/      small JSON aggregates the frontend actually loads
scripts/
  build_aggregates.py   raw CSV -> data/processed/*.json
web/
  index.html, style.css, app.js   the visualization itself
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

## Still to do

- [ ] Join case LON/LAT to Minneapolis neighborhood boundaries
- [ ] Build the by-neighborhood aggregate + map view
- [ ] Write up the November/December seasonal pattern
