"""A circle drawn on the sea-level map: the ocean cells inside it, judged together.

Owns: reading the per-cell test results saved by scripts/export_cells.py, choosing the cells for a
circle, and handing them to core/significance.py as ONE family. No statistics here.

Rules (docs/decisions/0005-spatial-selection.md and 0009):
  - A cell belongs to the circle when its CENTRE lies inside it (great-circle distance to the
    centre at most the radius). A cell whose centre is outside is left out, even if the circle
    overlaps it.
  - The radius is 75 to 250 km and at least 4 ocean cells must be inside.
  - The correction (Benjamini-Hochberg) runs across the cells inside THIS circle only, for the OLS
    and for the autocorrelation-adjusted Mann-Kendall p-values. A cell is rising or falling only
    when both are significant after that and the slopes agree in sign. Draw a different circle and
    the family, and so the verdicts, change.

The per-cell tests themselves (`summarise`) are computed once, offline, because they do not depend
on the circle. Only the correction does, so only the correction happens per request.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from trend_detective.core.significance import Item, assess_family
from trend_detective.core.summary import Summary
from trend_detective.process.selection import (
    MIN_CELLS,
    RADIUS_MAX_KM,
    RADIUS_MIN_KM,
    SelectionError,
    haversine_km,
)
from trend_detective.process.significance_json import significance_json

# The Summary fields kept per cell (the band is a chart aid and is not needed here)
RECORD_FIELDS = (
    "n_months", "n_years", "ols_per_decade", "ols_ci_per_decade", "ols_p", "ols_significant",
    "sen_per_decade", "mk_p", "mk_significant", "tests_agree", "warnings", "sentence",
    "n_eff", "r1", "mk_p_ar1", "mk_ar1_significant",
)  # fmt: skip


def summary_to_record(s: Summary) -> dict:
    """A summary as plain JSON: NaN becomes null."""

    def plain(v):
        if isinstance(v, (tuple, list)):
            return [plain(x) for x in v]
        if isinstance(v, (float, np.floating)):
            return float(v) if math.isfinite(float(v)) else None
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        return v

    return {name: plain(getattr(s, name)) for name in RECORD_FIELDS}


def summary_from_record(r: dict) -> Summary:
    """The inverse of summary_to_record."""
    nan = float("nan")

    def num(v):
        return nan if v is None else float(v)

    return Summary(
        n_months=int(r["n_months"]),
        n_years=float(r["n_years"]),
        ols_per_decade=num(r["ols_per_decade"]),
        ols_ci_per_decade=(num(r["ols_ci_per_decade"][0]), num(r["ols_ci_per_decade"][1])),
        ols_p=num(r["ols_p"]),
        ols_significant=bool(r["ols_significant"]),
        sen_per_decade=num(r["sen_per_decade"]),
        mk_p=num(r["mk_p"]),
        mk_significant=bool(r["mk_significant"]),
        tests_agree=bool(r["tests_agree"]),
        warnings=tuple(r["warnings"]),
        sentence=r["sentence"],
        n_eff=num(r["n_eff"]),
        r1=num(r["r1"]),
        mk_p_ar1=num(r["mk_p_ar1"]),
        mk_ar1_significant=bool(r["mk_ar1_significant"]),
    )


@dataclass(frozen=True)
class OceanCells:
    """The ocean cells with a series, each with its own test results."""

    k: np.ndarray  # position in the full lat x lon grid (land included), as the page numbers it
    lat: np.ndarray
    lon: np.ndarray
    summaries: list[Summary]
    unit: str
    dataset: str
    period: tuple[int, int]


def load(path: Path) -> OceanCells:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run scripts/export_cells.py first.")
    d = json.loads(path.read_text(encoding="utf-8"))
    cells = d["cells"]
    return OceanCells(
        k=np.array([c["k"] for c in cells], dtype=int),
        lat=np.array([c["lat"] for c in cells], dtype=float),
        lon=np.array([c["lon"] for c in cells], dtype=float),
        summaries=[summary_from_record(c["summary"]) for c in cells],
        unit=d["unit"],
        dataset=d["dataset"],
        period=(int(d["period"][0]), int(d["period"][1])),
    )


def cells_inside(cells: OceanCells, lat: float, lon: float, radius_km: float) -> np.ndarray:
    """Indices (into `cells`) of the cells whose centre is inside the circle."""
    if not RADIUS_MIN_KM <= radius_km <= RADIUS_MAX_KM:
        raise SelectionError(
            f"radius must be {RADIUS_MIN_KM:g} to {RADIUS_MAX_KM:g} km, got {radius_km:g}"
        )
    dist = haversine_km(lat, lon, cells.lat, cells.lon)
    inside = np.flatnonzero(dist <= radius_km)  # a centre exactly on the edge is inside
    if inside.size < MIN_CELLS:
        raise SelectionError(
            f"only {inside.size} ocean cell(s) have their centre inside the circle; "
            f"at least {MIN_CELLS} are needed"
        )
    return inside


def analyse_circle(cells: OceanCells, lat: float, lon: float, radius_km: float) -> dict:
    """The cells inside a drawn circle, corrected together and judged by both tests."""
    inside = cells_inside(cells, lat, lon, radius_km)
    items = [
        Item(cells.summaries[i], f"cell {cells.lat[i]:.2f}, {cells.lon[i]:.2f}", cells.unit)
        for i in inside
    ]
    verdicts = assess_family(items, "circle")
    counts = {v: 0 for v in ("rise", "fall", "unclear", "none", "no_data")}
    out = []
    for i, a in zip(inside, verdicts, strict=True):
        counts[a.verdict] += 1
        slope = cells.summaries[i].ols_per_decade
        out.append(
            {
                "k": int(cells.k[i]),
                "lat": float(cells.lat[i]),
                "lon": float(cells.lon[i]),
                "slope_per_decade": float(slope) if math.isfinite(slope) else None,
                "significance": significance_json(a),
            }
        )
    n_tests = verdicts[0].n_tests
    return {
        "dataset": cells.dataset,
        "unit": cells.unit,
        "period": list(cells.period),
        "centre": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "cells_inside": int(inside.size),
        "counts": counts,
        "expected_by_chance": verdicts[0].expected_by_chance,
        "note": (
            f"{n_tests} ocean cells have their centre inside the circle. They are corrected "
            "together (Benjamini-Hochberg), once for the OLS test and once for the "
            "autocorrelation-adjusted Mann-Kendall test. A cell counts as rising or falling only "
            "when both are significant after that and the two slopes agree in sign. A cell whose "
            "centre is outside the circle is not part of it."
        ),
        "cells": out,
    }
