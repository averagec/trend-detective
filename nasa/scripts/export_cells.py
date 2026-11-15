"""Export one sea level trend per ECCO ocean cell around Indonesia, for the map's CIRCLE tool.

Every number comes from core/: core.summary.summarise for each cell. The correction for testing
many cells is NOT done here: it depends on which cells a user's circle contains, so the server does
it for each drawn circle (process/ocean_circle.py, POST /api/ocean-circle, ADR 0009). This script
only saves each cell's own, uncorrected test results.

Input : data/processed/ocean_se_asia/ECCO_L4_SSH_05DEG_MONTHLY_V4R4_*.npz (via ocean_cities)
Output: web/public/data/indonesia_cells.json   what the page draws: slope, CI, yearly anomalies
        data/processed/ocean/ecco_cell_stats.json   each cell's test results, read by the server

    python scripts/export_cells.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_detective.core.summary import summarise  # noqa: E402
from trend_detective.process import ocean_cities as oc  # noqa: E402
from trend_detective.process.ocean_circle import summary_to_record  # noqa: E402

OUT = ROOT / "web" / "public" / "data" / "indonesia_cells.json"
STATS_OUT = ROOT / "data" / "processed" / "ocean" / "ecco_cell_stats.json"
BOX = (94.0, -12.0, 142.0, 7.0)  # west, south, east, north: the Indonesia box of ADR 0005
RADIUS_KM = (75.0, 250.0)  # circle limits of ADR 0005
MIN_CELLS = 4


def main() -> None:
    y0, lats, lons, ssh = oc.load_grid()
    rows = np.where((lats >= BOX[1]) & (lats <= BOX[3]))[0]
    cols = np.where((lons >= BOX[0]) & (lons <= BOX[2]))[0]
    years = ssh.shape[0] // 12
    slope, lo, hi, yearly = [], [], [], []
    stats = []  # each ocean cell's own, uncorrected test results (for the server)
    k = 0  # position in the full lat x lon grid, land cells included: the page numbers cells so
    for i in rows:
        for j in cols:
            s = ssh[:, i, j] * 1000.0
            if not np.isfinite(s).any():
                for a in (slope, lo, hi, yearly):
                    a.append(None)
                k += 1
                continue
            r = summarise(s, "mm", "cell")
            slope.append(round(float(r.ols_per_decade), 2))
            lo.append(round(float(r.ols_ci_per_decade[0]), 2))
            hi.append(round(float(r.ols_ci_per_decade[1]), 2))
            ann = np.nanmean(s[: years * 12].reshape(years, 12), axis=1)
            yearly.append([int(round(v * 10)) for v in ann - np.nanmean(ann)])
            stats.append(
                {
                    "k": k,
                    "lat": round(float(lats[i]), 3),
                    "lon": round(float(lons[j]), 3),
                    "summary": summary_to_record(r),
                }
            )
            k += 1
    payload = {
        "note": "Made by scripts/export_cells.py from core statistics. Do not edit.",
        "dataset": oc.PRODUCT,
        "unit": "mm",
        "period": [y0, y0 + years - 1],
        "lat": [round(float(lats[i]), 3) for i in rows],
        "lon": [round(float(lons[j]), 3) for j in cols],
        "cell_deg": round(float(abs(lats[1] - lats[0])), 3),
        "radius_km": list(RADIUS_KM),
        "min_cells": MIN_CELLS,
        "ocean_cells": len(stats),
        "method": (
            "OLS trend per cell with an autocorrelation-adjusted 95% interval and a Mann-Kendall "
            "test (core.summary). For a circle, the server takes the cells whose centre is inside "
            "it (ADR 0005) and corrects them together with Benjamini-Hochberg; a cell rises or "
            "falls clearly only when both tests are significant after that (ADR 0009)."
        ),
        "slope_mm_per_decade": slope,
        "ci_low": lo,
        "ci_high": hi,
        "yearly_anomaly_tenth_mm": yearly,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    STATS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATS_OUT.write_text(
        json.dumps(
            {
                "note": "Made by scripts/export_cells.py: each cell's own results, not corrected.",
                "dataset": oc.PRODUCT,
                "unit": "mm",
                "period": [y0, y0 + years - 1],
                "cells": stats,
            },
            separators=(",", ":"),
        )
    )
    print(f"{len(stats)} ocean cells -> {OUT.relative_to(ROOT)} and {STATS_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
