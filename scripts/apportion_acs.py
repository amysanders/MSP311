"""
Apportion ACS tract data to Minneapolis neighborhoods by areal overlap.

Usage (needs pandas + geopandas, installed in .venv):
    .venv/bin/python scripts/apportion_acs.py

Reads:  data/raw/neighborhoods.geojson
        data/raw/tl_2024_27_tract.zip               (filtered to Hennepin, COUNTYFP 053)
        data/raw/acs_2024_5yr_hennepin_tracts.json
Writes: data/processed/tract_neighborhood_crosswalk.csv   (one row per tract x neighborhood overlap)
        data/processed/neighborhood_demographics.csv      (one row per neighborhood)

Method (areal interpolation):
  1. Project both layers to a metric CRS and intersect them.
  2. For each tract/neighborhood piece, frac_of_tract = piece area / tract area.
  3. Counts (owner- and renter-occupied units) are extensive, so each piece gets
     count * frac_of_tract, and a neighborhood is the sum over its pieces.
  4. Median household income is NOT additive: a slice of a median isn't a median.
     The neighborhood value is instead a household-weighted average of the
     overlapping tracts' medians (weights = apportioned owner + renter units).
     It approximates, and is not, the neighborhood's true median.
  5. Suppressed income values (ACS uses large negative sentinels) are treated
     as missing: those tracts drop out of the income average, and
     income_coverage records how much of the neighborhood's households remain.
     If coverage is below MIN_INCOME_COVERAGE the income estimate is blanked
     (NaN): an average built from a small fraction of a neighborhood's
     households isn't a usable estimate of it.
  6. The two city and Census layers don't share exact boundaries, which leaves
     thin slivers (about 44% of pieces cover under 0.1% of their tract). They
     carry negligible households, so they stay in the sums, but n_tracts counts
     only tracts covering at least MIN_TRACT_SHARE of a neighborhood's area.

Assumption: households are spread evenly across each tract. That is weakest where
a tract holds large lakes, parks or industrial land, so treat small differences
between neighborhoods with caution.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

HENNEPIN_FIPS = "053"
AREA_CRS = "EPSG:26915"  # NAD83 / UTM zone 15N, metres; suits Minneapolis
MIN_INCOME_COVERAGE = 0.5  # blank income if less of the neighborhood's households than this have data
MIN_TRACT_SHARE = 0.01  # a tract "counts" toward n_tracts if it covers this share of the neighborhood


def load_acs():
    rows = json.loads((RAW / "acs_2024_5yr_hennepin_tracts.json").read_text())
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"]
    df = df.rename(
        columns={"B19013_001E": "income", "B25003_002E": "owner", "B25003_003E": "renter"}
    )
    for col in ("income", "owner", "renter"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.loc[df["income"] < 0, "income"] = np.nan  # ACS "suppressed" sentinel
    return df[["GEOID", "income", "owner", "renter"]]


def load_layers():
    neigh = gpd.read_file(RAW / "neighborhoods.geojson")[["BDNAME", "geometry"]]
    tracts = gpd.read_file(f"zip://{RAW / 'tl_2024_27_tract.zip'}")
    tracts = tracts[tracts["COUNTYFP"] == HENNEPIN_FIPS][["GEOID", "geometry"]]
    print(f"input CRS: neighborhoods={neigh.crs.to_string()}, tracts={tracts.crs.to_string()}")
    neigh, tracts = neigh.to_crs(AREA_CRS), tracts.to_crs(AREA_CRS)
    for name, layer in (("neighborhoods", neigh), ("tracts", tracts)):
        n_bad = int((~layer.geometry.is_valid).sum())
        if n_bad:
            print(f"repairing {n_bad} invalid {name} geometries")
            layer["geometry"] = layer.geometry.make_valid()
    return neigh, tracts


def build_crosswalk(neigh, tracts):
    pieces = gpd.overlay(tracts, neigh, how="intersection", keep_geom_type=True)
    pieces["overlap_m2"] = pieces.geometry.area
    tract_area = tracts.set_index("GEOID").geometry.area.rename("tract_m2")
    neigh_area = neigh.set_index("BDNAME").geometry.area.rename("neigh_m2")
    pieces = pieces.join(tract_area, on="GEOID").join(neigh_area, on="BDNAME")
    pieces["frac_of_tract"] = pieces["overlap_m2"] / pieces["tract_m2"]
    pieces["frac_of_neighborhood"] = pieces["overlap_m2"] / pieces["neigh_m2"]
    return pd.DataFrame(pieces[["GEOID", "BDNAME", "overlap_m2", "frac_of_tract", "frac_of_neighborhood"]])


def apportion(crosswalk, acs):
    df = crosswalk.merge(acs, on="GEOID", how="left")
    df["owner_part"] = df["owner"] * df["frac_of_tract"]
    df["renter_part"] = df["renter"] * df["frac_of_tract"]
    df["hh_part"] = df["owner_part"] + df["renter_part"]
    has_income = df["income"].notna()
    df["hh_income_ok"] = df["hh_part"].where(has_income, 0.0)
    df["income_x_hh"] = (df["income"] * df["hh_part"]).where(has_income, 0.0)

    g = df.groupby("BDNAME")
    material = df[df["frac_of_neighborhood"] >= MIN_TRACT_SHARE].groupby("BDNAME")
    out = pd.DataFrame(
        {
            "n_tracts": material["GEOID"].nunique(),
            "owner_units": g["owner_part"].sum(),
            "renter_units": g["renter_part"].sum(),
            "households": g["hh_part"].sum(),
            "tract_coverage": g["frac_of_neighborhood"].sum(),
            "_hh_income_ok": g["hh_income_ok"].sum(),
            "_income_x_hh": g["income_x_hh"].sum(),
        }
    )
    out["homeownership_rate"] = out["owner_units"] / out["households"]
    out["income_wtd_avg_of_tract_medians"] = out["_income_x_hh"] / out["_hh_income_ok"].replace(0, np.nan)
    out["income_coverage"] = out["_hh_income_ok"] / out["households"].replace(0, np.nan)
    out.loc[out["income_coverage"] < MIN_INCOME_COVERAGE, "income_wtd_avg_of_tract_medians"] = np.nan
    out = out.drop(columns=["_hh_income_ok", "_income_x_hh"]).reset_index().rename(columns={"BDNAME": "neighborhood"})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    acs = load_acs()
    neigh, tracts = load_layers()
    crosswalk = build_crosswalk(neigh, tracts)
    demo = apportion(crosswalk, acs)

    crosswalk.round(6).to_csv(OUT / "tract_neighborhood_crosswalk.csv", index=False)
    demo.round(4).to_csv(OUT / "neighborhood_demographics.csv", index=False)

    # --- sanity checks: a handful of summary numbers, not file contents ---
    print(f"\ncrosswalk: {len(crosswalk)} tract x neighborhood pieces from "
          f"{crosswalk['GEOID'].nunique()} tracts and {crosswalk['BDNAME'].nunique()} neighborhoods")
    per_tract = crosswalk.groupby("GEOID")["frac_of_tract"].sum()
    print(f"tracts inside city (fractions sum >= 0.99): {int((per_tract >= 0.99).sum())}; "
          f"straddling the city limit: {int((per_tract < 0.99).sum())} "
          f"(min sum {per_tract.min():.3f})")
    print(f"neighborhood area covered by tracts: min {demo['tract_coverage'].min():.4f}, "
          f"max {demo['tract_coverage'].max():.4f}")
    blanked = demo[demo["income_wtd_avg_of_tract_medians"].isna()]
    print(f"neighborhoods: {len(demo)}; income blanked (coverage < {MIN_INCOME_COVERAGE}): {len(blanked)} "
          f"-> {', '.join(f'{r.neighborhood} ({r.income_coverage:.0%})' for r in blanked.itertuples())}")
    print(f"n_tracts (>= {MIN_TRACT_SHARE:.0%} of neighborhood): min {demo['n_tracts'].min()}, "
          f"median {demo['n_tracts'].median():.0f}, max {demo['n_tracts'].max()}")
    owner, renter = demo["owner_units"].sum(), demo["renter_units"].sum()
    print(f"city total: {owner + renter:,.0f} occupied units, homeownership {owner / (owner + renter):.1%}")
    print(f"homeownership_rate range: {demo['homeownership_rate'].min():.1%} to {demo['homeownership_rate'].max():.1%}")
    inc = demo["income_wtd_avg_of_tract_medians"]
    print(f"income range: ${inc.min():,.0f} to ${inc.max():,.0f}")
    print(f"\nWrote {len(crosswalk)} rows to data/processed/tract_neighborhood_crosswalk.csv")
    print(f"Wrote {len(demo)} rows to data/processed/neighborhood_demographics.csv")
    print(f"columns: {list(demo.columns)}")


if __name__ == "__main__":
    main()
