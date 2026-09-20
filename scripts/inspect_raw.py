"""
Sanity-check the raw inputs for the demographics experiment: load each file and
print only its shape and column names (never the contents).

Usage (needs pandas + geopandas, installed in .venv):
    .venv/bin/python scripts/inspect_raw.py

Reads: data/raw/neighborhoods.geojson
       data/raw/tl_2024_27_tract.zip               (all of Minnesota; filtered to Hennepin)
       data/raw/acs_2024_5yr_hennepin_tracts.json  (Census API response)
"""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
HENNEPIN_FIPS = "053"


def report(label, df):
    print(f"\n{label}")
    print(f"  shape:   {df.shape}")
    print(f"  columns: {list(df.columns)}")


def inspect_neighborhoods():
    report("Minneapolis neighborhoods (neighborhoods.geojson)", gpd.read_file(RAW / "neighborhoods.geojson"))


def inspect_tracts():
    tracts = gpd.read_file(f"zip://{RAW / 'tl_2024_27_tract.zip'}")
    report("Census tracts, all of Minnesota (tl_2024_27_tract.zip)", tracts)
    hennepin = tracts[tracts["COUNTYFP"] == HENNEPIN_FIPS]
    report(f"Census tracts, Hennepin County only (COUNTYFP == {HENNEPIN_FIPS})", hennepin)


def inspect_acs():
    path = RAW / "acs_2024_5yr_hennepin_tracts.json"
    if not path.exists() or path.stat().st_size == 0:
        print(f"\nACS 2020-2024 5-year ({path.name})\n  MISSING or empty — not downloaded yet")
        return
    rows = json.loads(path.read_text())  # Census API: first row is the header
    report(f"ACS 2020-2024 5-year, Hennepin tracts ({path.name})", pd.DataFrame(rows[1:], columns=rows[0]))


if __name__ == "__main__":
    inspect_neighborhoods()
    inspect_tracts()
    inspect_acs()
