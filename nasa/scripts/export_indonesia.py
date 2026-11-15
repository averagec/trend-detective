"""Export sea-level trends for coastal Indonesian cities as one static JSON file for the map.

Every number comes from core/: core.summary.summarise per city (deseasonalised OLS with an
autocorrelation-adjusted CI, Mann-Kendall with Sen's slope), then core.trend.benjamini_hochberg
across all coastal cities, because the map tests every city at once. A city is shown as a clear
trend only when its adjusted p-value is below 0.05.

The file is static so the demo runs offline (AGENTS.md rule 5). Rebuild it after changing core/
or the cities:

    python scripts/build_indonesia_geo.py --ne-dir /path/to/natural-earth   (only if cities change)
    python scripts/export_indonesia.py

Output: web/public/data/indonesia_sea_level.json
"""

from __future__ import annotations

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


def r(x, n=3):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def main() -> None:
    y0, lats, lons, ssh = oc.load_grid()
    ocean = np.isfinite(ssh).all(axis=0)
    years = ssh.shape[0] // 12
    rows = []
    for city in oc.read_cities():
        row = {
            "name": city.name,
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
            anom = deseasonalize(series)
            row.update(
                {
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

    tested = [x for x in rows if "p" in x]
    adj = benjamini_hochberg([x["p"] for x in tested])
    for x, a in zip(tested, adj, strict=True):
        x["p_adjusted"] = r(a, 6)
        x["significant"] = bool(x.pop("_ols_significant") and a < 0.05)

    OUT.write_text(
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
                "tests": len(tested),
                "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "cities": rows,
            },
            separators=(",", ":"),
        )
    )
    sig = sum(x.get("significant", False) for x in rows)
    print(f"{len(rows)} cities, {len(tested)} coastal tested, {sig} with a clear trend")
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
