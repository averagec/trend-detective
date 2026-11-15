"""Add per-city series for HUMID, LAND T, VPD and EVAP to the CASES data, so a city clicked on any
map layer can be investigated as a case (MAP.EXE -> INVESTIGATE AS A CASE).

For each study city and variable: the MERRA-2 grid cell nearest to the city that has data (the
same rule as the TEMP and RAIN city series already in cases_data.json), months of the whole
calendar years 1980 to 2018. A city with no cell with data within 150 km (a land variable next to
the sea) gets no series for that variable. The "idn" place is the Maritime Southeast Asia box,
copied from regional_data.json, so the map's box card can start a case too.

No statistics here: the page sends these months to the analysis engine (POST /api/lineup).
Only the datasets named below are written: the others in cases_data.json are left as they are.

    python scripts/export_city_cases.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_detective.process.city_cases import calendar_years, nearest_cell  # noqa: E402

CASES = ROOT / "web" / "public" / "data" / "cases_data.json"
REGIONAL = ROOT / "web" / "public" / "data" / "regional_data.json"
CUBE = ROOT / "data" / "processed" / "cells" / "merra2_idn.npz"
CITIES = ROOT / "data" / "catalog" / "city_coordinates_idn.csv"
Y0, Y1 = 1980, 2018  # the project window (catalog/scope.py)
KELVIN = 273.15
SOURCE = "NASA MERRA-2 (GES DISC)"
# key (the map layer key) -> label, unit shown, cube variable, conversion to that unit
DATASETS = {
    "qv2m": ("Air humidity (2 m specific humidity)", "g/kg", lambda v: v),
    "tsurf": ("Land surface temperature", "°C", lambda v: v - KELVIN),
    "vpd": ("Dryness of the air (vapour pressure deficit)", "kPa", lambda v: v),
    "evap": ("Surface evaporation", "mm/day", lambda v: v),
}


def slug(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def box_months(regional: dict, variable: str, conv) -> list[float | None]:
    """The box's months in the same unit as the city series (regional_data.json keeps kelvin)."""
    layer = regional["layers"][f"merra2:{variable}"]
    box = next(r for r in layer["regions"] if r["key"] == "se_asia_maritime")
    by = {p["period"]: p["value"] for p in box["series"]}
    return [
        None if by.get(f"{y}-{m:02d}") is None else round(float(conv(by[f"{y}-{m:02d}"])), 4)
        for y in range(Y0, Y1 + 1)
        for m in range(1, 13)
    ]


def main() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    regional = json.loads(REGIONAL.read_text(encoding="utf-8"))
    idn = cases["datasets"]["t2m"]["regions"]["idn"]
    cities = list(csv.DictReader(CITIES.open(encoding="utf-8")))
    with np.load(CUBE) as z:
        lats, lons = np.asarray(z["lat"], float), np.asarray(z["lon"], float)
        for key, (label, unit, conv) in DATASETS.items():
            cube = conv(np.asarray(z[key], float))
            first = str(z[f"{key}__periods"][0])
            regions = {"idn": {"name": idn["name"], "long": idn["long"], "y0": Y0,
                               "monthly": box_months(regional, key, conv)}}  # fmt: skip
            skipped = []
            for c in cities:
                lat, lon = float(c["lat"]), float(c["lon"])
                hit = nearest_cell(cube, lats, lons, lat, lon)
                if hit is None:
                    skipped.append(c["city"])
                    continue
                i, j, km = hit
                months = calendar_years(cube[:, i, j], first, Y0, Y1)
                regions[slug(c["city"])] = {
                    "name": c["city"],
                    "long": f"{c['city']}; MERRA-2 cell at {lats[i]:.3f}, {lons[j]:.3f}, "
                    f"{km:.0f} km away",
                    "y0": Y0,
                    "monthly": [None if v is None else round(v, 4) for v in months],
                }
            cases["datasets"][key] = {
                "label": label, "unit": unit, "source": SOURCE, "start": Y0, "end": Y1,
                "regions": regions,
            }  # fmt: skip
            note = f" (no cell with data near: {', '.join(skipped)})" if skipped else ""
            print(f"{key}: {len(regions) - 1} cities + the box{note}")
    # utf-8 on purpose: the default encoding is cp1252 on Windows, which turns the degree sign
    # into a byte the browser cannot read
    CASES.write_text(
        json.dumps(cases, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
    )
    print(f"-> {CASES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
