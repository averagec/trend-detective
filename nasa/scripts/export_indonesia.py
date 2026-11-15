"""Export sea-level trends for coastal Indonesian cities as one static JSON file for the map.

Every number comes from core/: core.summary.summarise per city (deseasonalised OLS with an
autocorrelation-adjusted CI, Mann-Kendall with Sen's slope), then core.trend.benjamini_hochberg
across all coastal cities, because the map tests every city at once. A city is shown as a clear
trend only when its adjusted p-value is below 0.05.

The file is static so the demo runs offline (AGENTS.md rule 5). Rebuild it after changing core/
or the cities:

    python scripts/build_indonesia_geo.py --ne-dir /path/to/natural-earth   (only if cities change)
    python scripts/export_indonesia.py

Outputs:
    web/public/data/indonesia_sea_level.json  per-city trends, grids and charts for MAP.EXE
    web/public/data/cases_data.json           monthly series for the CASES workflow: ECCO sea
                                              level per coastal city, plus the MERRA-2 regional
                                              temperature and rain over Maritime Southeast Asia
                                              (from data/demo/json, made by build_processed.py)
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_detective.core.summary import summarise  # noqa: E402
from trend_detective.core.trend import benjamini_hochberg, deseasonalize  # noqa: E402
from trend_detective.process import ocean_cities as oc  # noqa: E402

OUT = ROOT / "web" / "public" / "data" / "indonesia_sea_level.json"
OUT_CASES = ROOT / "web" / "public" / "data" / "cases_data.json"
MERRA_DIR = ROOT / "data" / "demo" / "json" / "se_asia_maritime"
KELVIN = 273.15


def write_utf8(path: Path, text: str) -> None:
    """Write JSON as UTF-8. The default encoding is cp1252 on Windows, which turns the degree sign
    into a byte the browser cannot read."""
    path.write_text(text, encoding="utf-8")


def slug(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def core_stats(s) -> dict:
    """The full-record result from core.summary, for the app to show next to its own lineup."""
    return {
        "per_decade": r(s.ols_per_decade, 3),
        "ci_per_decade": [r(s.ols_ci_per_decade[0], 3), r(s.ols_ci_per_decade[1], 3)],
        "p": r(s.ols_p, 6),
        "significant": bool(s.ols_significant),
        "sentence": s.sentence,
    }


WITNESS = ROOT / "data" / "processed" / "witness" / "witness_regional.csv"
REGIONAL = ROOT / "web" / "public" / "data" / "regional_data.json"


def grace_dataset() -> dict:
    """GRACE / GRACE-FO water storage for the Maritime Southeast Asia box (gaps as null).

    The core numbers are the ones in regional_data.json (scripts/export_regional.py), so the map
    card and the case show the same result.
    """
    vals = {}
    with WITNESS.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["dataset"] == "grace" and row["region"] == "se_asia_maritime":
                vals[row["period"]] = float(row["value"])
    y0, y1 = int(min(vals)[:4]), int(max(vals)[:4])
    monthly = [vals.get(f"{y}-{m:02d}") for y in range(y0, y1 + 1) for m in range(1, 13)]
    reg = json.loads(REGIONAL.read_text())["layers"]["grace:grace_lwe"]["regions"]
    st = next(x for x in reg if x["key"] == "se_asia_maritime")
    return {
        "label": "Water stored on land",
        "unit": "cm",
        "source": "NASA GRACE / GRACE-FO (JPL mascons)",
        "start": y0,
        "end": y1 - 1,
        "regions": {
            "idn": {
                "name": "Maritime Southeast Asia",
                "long": st["name"],
                "y0": y0,
                "monthly": [None if v is None else r(v, 3) for v in monthly],
                "core": {
                    "per_decade": r(st["slope_per_decade"], 3),
                    "ci_per_decade": [r(st["ci_low"], 3), r(st["ci_high"], 3)],
                    "p": r(st["ols_p_adj"], 6),
                    "significant": bool(st["ols_p_adj"] < 0.05),
                    "sentence": st["sentence"].replace("grace_lwe", "Water stored on land"),
                },
            }
        },
    }


def merra_dataset(var: str, label: str, unit: str, to_unit) -> dict:
    """One MERRA-2 regional series from the processed demo JSON (stats already from core)."""
    d = json.loads((MERRA_DIR / f"{var}.json").read_text())
    st = d["statistics"]
    full_years = [int(x["period"][:4]) for x in d["series"]]
    end = max(y for y in set(full_years) if full_years.count(y) == 12)
    return {
        "label": label,
        "unit": unit,
        "source": "NASA MERRA-2 (GES DISC)",
        "start": full_years[0],
        "end": end,
        "regions": {
            "idn": {
                "name": "Maritime Southeast Asia",
                "long": d["region_name"],
                "y0": full_years[0],
                "monthly": [r(to_unit(x["value"]), 3) for x in d["series"]],
                "core": {
                    "per_decade": r(st["ols_per_decade"], 3),
                    "ci_per_decade": [r(v, 3) for v in st["ols_ci_per_decade"]],
                    "p": r(st["ols_p"], 6),
                    "significant": bool(st["ols_significant"]),
                    "sentence": d["sentence"],
                    "period": [d["first_month"], d["last_month"]],
                },
            }
        },
    }


def r(x, n=3):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def main() -> None:
    y0, lats, lons, ssh = oc.load_grid()
    ocean = np.isfinite(ssh).all(axis=0)
    years = ssh.shape[0] // 12
    step = float(abs(lats[1] - lats[0]))
    rows = []
    case_regions: dict[str, dict] = {}
    for city in oc.read_cities():
        row = {
            "name": city.name,
            "region": city.region,
            "province": city.province,
            "lat": city.lat,
            "lon": city.lon,
            "population": city.population,
            "capital": city.capital,
            "coast_km": city.coast_km,
            "coastal": city.coastal,
        }
        cells = oc.nearest_cells(city, lats, lons, ocean) if city.coastal else []
        if city.coastal and cells:
            series = oc.city_series(city, lats, ssh, cells)
            s = summarise(series, "mm", f"Sea level near {city.name}")
            case_regions[slug(city.name)] = {
                "name": city.name,
                "y0": y0,
                "monthly": [r(v, 2) for v in series],
                "core": core_stats(s),
            }
            anom = deseasonalize(series)
            row.update(
                {
                    "case": slug(city.name),
                    "cells": len(cells),
                    "nearest_cell_km": r(cells[0][2], 1),
                    "trend_mm_per_decade": r(s.ols_per_decade, 2),
                    "trend_mm_per_year": r(s.ols_per_decade / 10, 2),
                    "ci_mm_per_decade": [
                        r(s.ols_ci_per_decade[0], 2),
                        r(s.ols_ci_per_decade[1], 2),
                    ],
                    "p": r(s.ols_p, 6),
                    "sen_mm_per_decade": r(s.sen_per_decade, 2),
                    "mk_p_unadjusted": r(s.mk_p, 6),
                    "tests_agree": s.tests_agree,
                    "warnings": list(s.warnings),
                    "sentence": s.sentence,
                    "annual_anomaly_mm": [
                        [y0 + k, r(np.nanmean(anom[k * 12 : k * 12 + 12]), 2)] for k in range(years)
                    ],
                    "line_mm": [
                        [y0 + k, r(f, 2), r(lo, 2), r(hi, 2)] for k, f, lo, hi in s.ols_band_by_year
                    ],
                    "_ols_significant": s.ols_significant,
                }
            )
        elif city.coastal:
            row["note"] = "No ECCO ocean cell within reach of this city."
        else:
            row["note"] = f"Inland, {city.coast_km:.0f} km from the sea: sea level does not apply."
        rows.append(row)

    for x in rows:
        if not x["coastal"]:
            near = min(
                (y for y in rows if "p" in y),
                key=lambda y: oc.km(x["lat"], x["lon"], y["lat"], y["lon"]),
            )
            x["nearest_coastal"] = {
                "name": near["name"],
                "km": r(oc.km(x["lat"], x["lon"], near["lat"], near["lon"]), 0),
            }

    tested = [x for x in rows if "p" in x]
    adj = benjamini_hochberg([x["p"] for x in tested])
    for x, a in zip(tested, adj, strict=True):
        x["p_adjusted"] = r(a, 6)
        x["significant"] = bool(x.pop("_ols_significant") and a < 0.05)

    write_utf8(OUT, 
        json.dumps(
            {
                "variable": "Sea level next to the city (ECCO dynamic sea surface height)",
                "dataset": f"{oc.PRODUCT} (NASA PO.DAAC), 0.5 degree, monthly",
                "period": [y0, y0 + years - 1],
                "unit": "mm",
                "method": (
                    "Nearest ocean cells (up to 4, within 120 km), cos(latitude) mean. "
                    "Monthly series deseasonalised; OLS trend with autocorrelation-adjusted "
                    "95% CI; Mann-Kendall with Sen's slope; Benjamini-Hochberg across all "
                    "coastal cities."
                ),
                "caveat": (
                    "Ocean-model sea level next to the coast. It does not include land "
                    "sinking, which is a large part of flooding in Jakarta and Semarang."
                ),
                "grid": {
                    "cell_deg": step,
                    "radius_km": oc.MAX_KM,
                    "domain": [
                        r(float(lons.min()) - step / 2, 2),
                        r(float(lats.min()) - step / 2, 2),
                        r(float(lons.max()) + step / 2, 2),
                        r(float(lats.max()) + step / 2, 2),
                    ],
                    "note": (
                        "The city trend averages every ocean cell whose centre is within "
                        "120 km of the city (0.5 degree ECCO cells)."
                    ),
                },
                "tests": len(tested),
                "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "cities": rows,
            },
            separators=(",", ":"),
        )
    )
    write_utf8(OUT_CASES, 
        json.dumps(
            {
                "note": "Made by scripts/export_indonesia.py from NASA data; do not edit.",
                "datasets": {
                    "ssl": {
                        "label": "Sea level at the coast",
                        "unit": "mm",
                        "source": "NASA ECCO V4r4 (PO.DAAC)",
                        "start": y0,
                        "end": y0 + years - 1,
                        "regions": case_regions,
                    },
                    "t2m": merra_dataset(
                        "t2m", "Air temperature (2 m)", "°C", lambda k: k - KELVIN
                    ),
                    "precip": merra_dataset("precip", "Rainfall", "mm/day", lambda v: v),
                    "tws": grace_dataset(),
                },
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    sig = sum(x.get("significant", False) for x in rows)
    print(f"{len(rows)} cities, {len(tested)} coastal tested, {sig} with a clear trend")
    print(f"-> {OUT.relative_to(ROOT)} and {OUT_CASES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
