"""
Fast, dependency-free unit tests for the pure logic in scripts/build_aggregates.py.

These use small made-up rows and shapes, not the real 292k-row dataset, so they
run instantly and stay meaningful even as the raw data changes. For checks
against the real data files, see test_data_integrity.py.

Run: .venv/bin/python -m pytest tests/
"""

import build_aggregates as agg


def row(lon, lat, resolution_hours=""):
    """A minimal CSV row dict with only the columns has_location/location_of read."""
    return {"LON": str(lon), "LAT": str(lat), "resolution_hours": resolution_hours}


class TestHasLocation:
    def test_real_coordinates(self):
        assert agg.has_location(row(-93.27, 44.98)) is True

    def test_zero_zero_is_unknown(self):
        assert agg.has_location(row(0, 0)) is False

    def test_lon_zero_alone_still_counts_as_unknown(self):
        # Known quirk: has_location requires BOTH to be nonzero. A real point
        # with lon exactly 0.0 (nowhere near Minneapolis in practice) would be
        # misclassified as unknown. Documented here so a future "fix" is a
        # deliberate choice, not an accidental behavior change.
        assert agg.has_location(row(0, 44.98)) is False

    def test_lat_zero_alone_still_counts_as_unknown(self):
        assert agg.has_location(row(-93.27, 0)) is False


class TestLocationOf:
    def test_returns_float_tuple_for_located_case(self):
        assert agg.location_of(row(-93.27, 44.98)) == (-93.27, 44.98)

    def test_returns_sentinel_for_unlocated_case(self):
        assert agg.location_of(row(0, 0)) == agg.UNKNOWN_LOCATION


class TestPercentile:
    def test_median_ish_point(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        assert agg.percentile(values, 0.5) == 6.0  # idx = int(10*0.5) = 5 -> values[5]

    def test_p90_of_ten_values(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        assert agg.percentile(values, 0.90) == 10.0

    def test_p0_is_the_minimum(self):
        values = [3.0, 5.0, 9.0]
        assert agg.percentile(values, 0.0) == 3.0

    def test_never_indexes_past_the_end(self):
        # p=1.0 on n values would index out of range without the min(..., n-1) guard.
        values = [3.0, 5.0, 9.0]
        assert agg.percentile(values, 1.0) == 9.0

    def test_rounds_to_one_decimal(self):
        assert agg.percentile([1.234, 5.678], 0.0) == 1.2


# A 10x10 square, (x=lon, y=lat) to match how GeoJSON coordinates are read.
SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]


class TestPointInRing:
    def test_point_well_inside(self):
        assert agg.point_in_ring(5, 5, SQUARE) is True

    def test_point_well_outside(self):
        assert agg.point_in_ring(15, 15, SQUARE) is False

    def test_point_outside_on_one_axis(self):
        assert agg.point_in_ring(5, 15, SQUARE) is False


def make_neighborhood(name, outer, holes=(), id_="1"):
    xs = [x for x, _ in outer]
    ys = [y for _, y in outer]
    return {
        "name": name,
        "id": id_,
        "rings": [outer, *holes],
        "bbox": (min(xs), min(ys), max(xs), max(ys)),
    }


class TestFindNeighborhood:
    def setup_method(self):
        # Neighborhood A: a plain square, no holes.
        self.a = make_neighborhood("A", [(0, 0), (10, 0), (10, 10), (0, 10)])
        # Neighborhood B: a square with a square hole cut out of its middle.
        self.b = make_neighborhood(
            "B",
            outer=[(20, 0), (30, 0), (30, 10), (20, 10)],
            holes=[[(24, 4), (26, 4), (26, 6), (24, 6)]],
        )
        self.neighborhoods = [self.a, self.b]

    def test_point_inside_a(self):
        assert agg.find_neighborhood(5, 5, self.neighborhoods) == "A"

    def test_point_inside_b_outside_the_hole(self):
        assert agg.find_neighborhood(21, 1, self.neighborhoods) == "B"

    def test_point_inside_bs_hole_is_outside_neighborhoods(self):
        assert agg.find_neighborhood(25, 5, self.neighborhoods) == agg.OUTSIDE_NEIGHBORHOODS

    def test_point_in_neither_bbox(self):
        assert agg.find_neighborhood(100, 100, self.neighborhoods) == agg.OUTSIDE_NEIGHBORHOODS

    def test_point_in_gap_between_a_and_b(self):
        # Inside neither bbox at x=15, so this also exercises the bbox prefilter
        # actually skipping a neighborhood rather than false-matching it.
        assert agg.find_neighborhood(15, 5, self.neighborhoods) == agg.OUTSIDE_NEIGHBORHOODS
