"""Export one sea level trend per ECCO ocean cell around Indonesia, for the map's CIRCLE tool.

Every number comes from core/: core.summary.summarise for each cell, then
core.trend.benjamini_hochberg across all exported cells (so "clear rise" means the same thing
wherever the circle is drawn). The page only counts and lists these results; it computes no
statistics. Yearly anomalies are included for the circle's chart (processing, not a test).

Input : data/processed/ocean_se_asia/ECCO_L4_SSH_05DEG_MONTHLY_V4R4_*.npz (via ocean_cities)
Output: web/public/data/indonesia_cells.json

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
from trend_detective.core.trend import benjamini_hochberg  # noqa: E402
from trend_detective.process import ocean_cities as oc  # noqa: E402

OUT = ROOT / "web" / "public" / "data" / "indonesia_cells.json"
BOX = (94.0, -12.0, 142.0, 7.0)  # west, south, east, north: the Indonesia box of ADR 0005
RADIUS_KM = (75.0, 250.0)  # circle limits of ADR 0005
MIN_CELLS = 4


def main() -> None:
    y0, lats, lons, ssh = oc.load_grid()
    rows = np.where((lats >= BOX[1]) & (lats <= BOX[3]))[0]
    cols = np.where((lons >= BOX[0]) & (lons <= BOX[2]))[0]
    years = ssh.shape[0] // 12
    slope, lo, hi, p, yearly = [], [], [], [], []
    for i in rows:
        for j in cols:
            s = ssh[:, i, j] * 1000.0
            if not np.isfinite(s).any():
                for a in (slope, lo, hi, p, yearly):
                    a.append(None)
                continue
            r = summarise(s, "mm", "cell")
            slope.append(round(float(r.ols_per_decade), 2))
            lo.append(round(float(r.ols_ci_per_decade[0]), 2))
            hi.append(round(float(r.ols_ci_per_decade[1]), 2))
            p.append(float(r.ols_p))
            ann = np.nanmean(s[: years * 12].reshape(years, 12), axis=1)
            yearly.append([int(round(v * 10)) for v in ann - np.nanmean(ann)])
    sea = [k for k, v in enumerate(p) if v is not None]
    adj = benjamini_hochberg(np.array([p[k] for k in sea]))
    p_adj: list[float | None] = [None] * len(p)
    for k, v in zip(sea, adj, strict=True):
        p_adj[k] = float(v)
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
        "tests": len(sea),
        "method": (
            "OLS trend per cell with an autocorrelation-adjusted 95% interval (core.summary), "
            f"Benjamini-Hochberg across all {len(sea)} ocean cells in the box. A cell counts "
            "when its centre is inside the circle (ADR 0005)."
        ),
        "slope_mm_per_decade": slope,
        "ci_low": lo,
        "ci_high": hi,
        "p_adjusted": [None if v is None else float(f"{v:.3g}") for v in p_adj],
        "yearly_anomaly_tenth_mm": yearly,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    sig = sum(1 for v in p_adj if v is not None and v < 0.05)
    print(f"{len(sea)} ocean cells, {sig} with a clear trend -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
