import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="session")
def raw_rows():
    """All rows of the raw 311 CSV, loaded once and reused across tests."""
    import build_aggregates as agg

    with open(agg.RAW_CSV, newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def overall():
    return json.loads((ROOT / "data" / "processed" / "overall.json").read_text())


@pytest.fixture(scope="session")
def by_neighborhood():
    return json.loads((ROOT / "data" / "processed" / "by_neighborhood.json").read_text())


@pytest.fixture(scope="session")
def by_type():
    return json.loads((ROOT / "data" / "processed" / "by_type.json").read_text())


@pytest.fixture(scope="session")
def neighborhoods_geojson():
    return json.loads((ROOT / "data" / "processed" / "neighborhoods.geojson").read_text())
