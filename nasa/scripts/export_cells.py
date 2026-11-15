"""Export one trend per grid cell around Indonesia, per map layer, for the map's CIRCLE tool.

Every number comes from core/: core.summary.summarise for each cell, then
core.trend.benjamini_hochberg across all cells of that layer (so "clear trend" means the same
wherever the circle is drawn). The page only counts and lists these results; it computes no
statistics. Yearly anomalies (seasons removed) are included for the circle's chart.

Layers and inputs (a layer is skipped, with a note, when its input is missing):
    ssl     sea level, ECCO V4r4 0.5 deg   data/processed/ocean_se_asia/*.npz (via ocean_cities)
    t2m     air temperature, MERRA-2        data/processed/cells/merra2_idn.npz  (cell_cube.py)
    precip  rainfall, MERRA-2               data/processed/cells/merra2_idn.npz  (cell_cube.py)
    tws     water stored on land, GRACE     data/processed/cells/grace_idn.npz   (not built yet)

Output: web/public/data/indonesia_cells.json

    python scripts/export_cells.py
    python scripts/export_cells.py --cells-dir some/other/cells
"""

from __future__ import annotations

import argparse
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
CELLS = ROOT / "data" / "processed" / "cells"
BOX = (94.0, -12.0, 142.0, 7.0)  # west, south, east, north: the Indonesia box of ADR 0005
RADIUS_KM = (75.0, 250.0)  # circle limits of ADR 0005
MIN_CELLS = 4
KELVIN = 273.15
# layer -> (cube file, variable in it, unit shown, convert raw values to that unit, dataset name)
CUBES = {
    "t2m": ("merra2_idn.npz", "t2m", "°C", lambda v: v - KELVIN, "NASA MERRA-2 (GES DISC)"),
    "precip": ("merra2_idn.npz", "precip", "mm/day", lambda v: v, "NASA MERRA-2 (GES DISC)"),
    "tws": ("grace_idn.npz", "grace_lwe", "cm", lambda v: v, "NASA GRACE / GRACE-FO"),
}


def to_january(values: np.ndarray, first: str) -> tuple[int, np.ndarray]:
    """Pad the front with NaN so the series starts in January (summarise expects that)."""
    y0, m0 = int(first[:4]), int(first[5:7])
    pad = np.full((m0 - 1,) + values.shape[1:], np.nan)
    return y0, np.concatenate([pad, values]) if m0 > 1 else values


def layer_payload(y0: int, cube: np.ndarray, lats, lons, unit: str, dataset: str) -> dict:
    """Core trend per cell (cube shaped months x lat x lon, January first), BH across cells."""
    rows = np.where((lats >= BOX[1]) & (lats <= BOX[3]))[0]
    cols = np.where((lons >= BOX[0]) & (lons <= BOX[2]))[0]
    n = cube.shape[0]
    years = -(-n // 12)
    full = np.full((years * 12,) + cube.shape[1:], np.nan)
    full[:n] = cube
    slope, lo, hi, p, yearly = [], [], [], [], []
    for i in rows:
        for j in cols:
            s = full[:, i, j]
            if np.isfinite(s).sum() < 24:
                for a in (slope, lo, hi, p, yearly):
                    a.append(None)
                continue
            r = summarise(s[:n], unit, "cell")
            slope.append(round(float(r.ols_per_decade), 4))
            lo.append(round(float(r.ols_ci_per_decade[0]), 4))
            hi.append(round(float(r.ols_ci_per_decade[1]), 4))
            p.append(float(r.ols_p))
            m = s.reshape(years, 12)
            clim = np.nanmean(m, axis=0)
            anom = m - clim
            ok = np.isfinite(anom).sum(axis=1) >= 6
            with np.errstate(all="ignore"):
                ann = np.where(ok, np.nanmean(anom, axis=1), np.nan)
            yearly.append([None if not np.isfinite(v) else round(float(v), 3) for v in ann])
    valid = [k for k, v in enumerate(p) if v is not None]
    adj = benjamini_hochberg(np.array([p[k] for k in valid]))
    p_adj: list[float | None] = [None] * len(p)
    for k, v in zip(valid, adj, strict=True):
        p_adj[k] = float(f"{v:.3g}")
    return {
        "dataset": dataset,
        "unit": unit,
        "period": [y0, y0 + years - 1],
        "lat": [round(float(lats[i]), 3) for i in rows],
        "lon": [round(float(lons[j]), 3) for j in cols],
        "cell_deg": [
            round(float(abs(lats[1] - lats[0])), 3),
            round(float(abs(lons[1] - lons[0])), 3),
        ],
        "tests": len(valid),
        "slope_per_decade": slope,
        "ci_low": lo,
        "ci_high": hi,
        "p_adjusted": p_adj,
        "yearly_anomaly": yearly,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--cells-dir", type=Path, default=CELLS)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    layers, skipped = {}, {}
    y0, lats, lons, ssh = oc.load_grid()
    layers["ssl"] = layer_payload(y0, ssh * 1000.0, lats, lons, "mm", oc.PRODUCT)
    for key, (fname, var, unit, conv, dataset) in CUBES.items():
        path = a.cells_dir / fname
        if not path.exists():
            skipped[key] = f"{path.name} not found (build it with process/cell_cube.py)"
            continue
        with np.load(path) as z:
            if var not in z.files:
                skipped[key] = f"{var} not in {path.name}"
                continue
            lat, lon = np.asarray(z["lat"], float), np.asarray(z["lon"], float)
            first = str(z[f"{var}__periods"][0])
            cube = conv(np.asarray(z[var], float))
        if lat[0] > lat[-1]:
            lat, cube = lat[::-1], cube[:, ::-1, :]
        y, cube = to_january(cube, first)
        layers[key] = layer_payload(y, cube, lat, lon, unit, dataset)
    payload = {
        "note": "Made by scripts/export_cells.py from core statistics. Do not edit.",
        "radius_km": list(RADIUS_KM),
        "min_cells": MIN_CELLS,
        "method": (
            "OLS trend per grid cell with an autocorrelation-adjusted 95% interval "
            "(core.summary), Benjamini-Hochberg across all cells of the layer. A cell counts "
            "when its centre is inside the circle (ADR 0005)."
        ),
        "layers": layers,
        "skipped": skipped,
    }
    a.out.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    for k, v in layers.items():
        sig = sum(1 for q in v["p_adjusted"] if q is not None and q < 0.05)
        print(f"{k}: {v['tests']} cells, {sig} with a clear trend")
    for k, why in skipped.items():
        print(f"skipped {k}: {why}")


if __name__ == "__main__":
    main()
