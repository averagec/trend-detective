"""Flood and drought incidents (GDIS) for a city or a circle, 1980 to 2018.

Owns: choosing the cells (the city's cell, or the cells whose centres lie in the circle), summing
counts over the circle, and laying the results out for the page. No statistics here: trends come
from core/counts.py, and the Benjamini-Hochberg adjustment from core/trend.py.

Input : data/processed/gdis/gdis_counts_idn.npz  (process/gdis.py)
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np

from trend_detective.core.counts import count_trend
from trend_detective.core.trend import benjamini_hochberg
from trend_detective.process.selection import Grid, circle_cells, city_cell

HAZARDS = ("flood", "drought")


def load_counts(path: Path) -> dict:
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} not found. Run process/gdis.py first.")
    z = np.load(path)
    return {
        "lat": np.asarray(z["lat"]),
        "lon": np.asarray(z["lon"]),
        "years": np.asarray(z["years"]),
        **{h: np.asarray(z[h]) for h in HAZARDS},
    }


def _trend(series: np.ndarray) -> dict:
    res = count_trend(series)
    out = asdict(res)
    out["warnings"] = list(res.warnings)
    return out


def city(data: dict, hazard: str, lat: float, lon: float) -> dict:
    grid = Grid(data["lat"], data["lon"])
    cell = city_cell(grid, lat, lon)
    series = data[hazard][:, cell.i, cell.j].astype(float)
    return {
        "hazard": hazard,
        "cell": {
            "lat": cell.lat,
            "lon": cell.lon,
            "width_km": round(cell.width_km, 1),
            "height_km": round(cell.height_km, 1),
        },
        "years": [int(y) for y in data["years"]],
        "counts": [int(v) for v in series],
        "trend": _trend(series),
    }


def circle(data: dict, hazard: str, lat: float, lon: float, radius_km: float) -> dict:
    """Cells whose centres lie in the circle. Each cell is tested on its own, the test is adjusted
    across cells (Benjamini-Hochberg), and the combined count over the circle is tested too."""
    grid = Grid(data["lat"], data["lon"])
    cells = circle_cells(grid, lat, lon, radius_km)  # refuses fewer than 4 cells
    stack = np.stack([data[hazard][:, c.i, c.j] for c in cells], axis=1).astype(
        float
    )  # years x cells
    per_cell = [count_trend(stack[:, k]) for k in range(stack.shape[1])]
    adjusted = benjamini_hochberg([t.mk_p for t in per_cell])
    rows = []
    for c, t, p_adj in zip(cells, per_cell, adjusted, strict=True):
        significant = bool(p_adj < 0.05)
        direction = (
            ("rise" if t.sen_per_decade > 0 else "fall" if t.sen_per_decade < 0 else "none")
            if significant
            else "none"
        )
        rows.append(
            {
                "lat": c.lat,
                "lon": c.lon,
                "total": t.total,
                "sen_per_decade": t.sen_per_decade,
                "p_adjusted": float(p_adj),
                "direction": direction,
            }
        )
    combined = stack.sum(axis=1)
    return {
        "hazard": hazard,
        "radius_km": radius_km,
        "cells_in_circle": len(cells),
        "years": [int(y) for y in data["years"]],
        "combined": {"counts": [int(v) for v in combined], "trend": _trend(combined)},
        "cells": rows,
        "agreement": {
            "rising": sum(r["direction"] == "rise" for r in rows),
            "falling": sum(r["direction"] == "fall" for r in rows),
            "not_significant": sum(r["direction"] == "none" for r in rows),
        },
    }
