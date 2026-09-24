"""
Checks against the ACTUAL current data files (not synthetic fixtures): the raw
CSV, and the outputs of `python3 scripts/build_aggregates.py`. These catch the
kind of thing that got checked by hand, ad hoc, throughout this project's
early sessions -- duplicate case IDs, bad coordinates, row counts not adding
up across the pipeline -- so a bad data refresh or a pipeline bug fails loudly
here instead of silently reaching the page.

If data/raw or data/processed changes, re-run `python3 scripts/build_aggregates.py`
before running these, or they'll be checking a stale processed/ against a
fresher raw/ (or vice versa).

Run: .venv/bin/python -m pytest tests/test_data_integrity.py
"""

# Generously padded around Minneapolis; wide enough to allow real variation,
# tight enough to catch a sign flip, a stray decimal, or a wrong-country typo.
CITY_LON_RANGE = (-93.40, -93.10)
CITY_LAT_RANGE = (44.80, 45.15)

DOCUMENTED_CUTOFF = ("2023-07-01", "2026-06-30")  # see README's "Cutoff" note


class TestRawCsv:
    def test_no_duplicate_case_ids(self, raw_rows):
        ids = [r["CASEID"] for r in raw_rows]
        assert len(ids) == len(set(ids))

    def test_no_negative_resolution_hours(self, raw_rows):
        bad = [r["CASEID"] for r in raw_rows if r["resolution_hours"] and float(r["resolution_hours"]) < 0]
        assert bad == []

    def test_resolution_hours_present_iff_closed_date_present(self, raw_rows):
        mismatched = [
            r["CASEID"]
            for r in raw_rows
            if bool(r["resolution_hours"]) != bool(r["CLOSEDDATETIME"])
        ]
        assert mismatched == []

    def test_case_status_is_only_open_or_closed(self, raw_rows):
        assert {r["CASESTATUS"] for r in raw_rows} <= {"0", "1"}

    def test_coordinates_are_placeholder_zero_or_within_city_bbox(self, raw_rows):
        bad = []
        for r in raw_rows:
            lon, lat = float(r["LON"]), float(r["LAT"])
            if lon == 0 and lat == 0:
                continue  # the documented "unknown location" placeholder
            in_range = CITY_LON_RANGE[0] <= lon <= CITY_LON_RANGE[1] and CITY_LAT_RANGE[0] <= lat <= CITY_LAT_RANGE[1]
            if not in_range:
                bad.append((r["CASEID"], lon, lat))
        assert bad == [], f"{len(bad)} case(s) outside the city bbox and not (0,0), e.g. {bad[:5]}"

    def test_opened_dates_within_documented_cutoff(self, raw_rows):
        dates = [r["OPENEDDATETIME"][:10] for r in raw_rows]
        assert min(dates) >= DOCUMENTED_CUTOFF[0], "a case opens before the README's stated cutoff"
        assert max(dates) <= DOCUMENTED_CUTOFF[1], "a case opens after the README's stated cutoff"


class TestOverallJson:
    def test_total_matches_raw_row_count(self, overall, raw_rows):
        assert overall["n_total_cases"] == len(raw_rows)

    def test_open_plus_closed_equals_total(self, overall):
        assert overall["n_open"] + overall["n_closed"] == overall["n_total_cases"]

    def test_unknown_location_count_matches_raw(self, overall, raw_rows):
        n_unknown = sum(1 for r in raw_rows if float(r["LON"]) == 0 and float(r["LAT"]) == 0)
        assert overall["n_unknown_location"] == n_unknown

    def test_date_range_matches_documented_cutoff(self, overall):
        assert (overall["first_opened"], overall["last_opened"]) == DOCUMENTED_CUTOFF


class TestByNeighborhoodJson:
    def test_has_exactly_87_neighborhoods(self, by_neighborhood):
        assert len(by_neighborhood["neighborhoods"]) == 87

    def test_case_counts_conserve_against_overall_total(self, by_neighborhood, overall):
        total = (
            sum(n["n_cases"] for n in by_neighborhood["neighborhoods"])
            + by_neighborhood["Unknown location"]["n_cases"]
            + by_neighborhood["Outside neighborhoods"]["n_cases"]
        )
        assert total == overall["n_total_cases"]

    def test_no_neighborhood_is_empty(self, by_neighborhood):
        empty = [n["neighborhood"] for n in by_neighborhood["neighborhoods"] if n["n_cases"] == 0]
        assert empty == []

    def test_neighborhood_names_match_the_geojson(self, by_neighborhood, neighborhoods_geojson):
        json_names = {n["neighborhood"] for n in by_neighborhood["neighborhoods"]}
        geo_names = {f["properties"]["name"] for f in neighborhoods_geojson["features"]}
        assert json_names == geo_names


class TestByTypeJson:
    def test_case_counts_conserve_against_closed_total(self, by_type, overall):
        # by_type.json only counts closed cases (see its module docstring).
        assert sum(t["n"] for t in by_type) == overall["n_closed"]

    def test_no_duplicate_type_names(self, by_type):
        names = [t["type"] for t in by_type]
        assert len(names) == len(set(names))
