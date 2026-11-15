"""Monthly series for the flood and drought flow. Owns: reading the indicator files, aligning series
on one monthly timeline, and converting rainfall rates to monthly totals. No statistics here.
Needs numpy only (plus local files; no network).

Inputs : data/processed/cells/<dataset>_idn.npz           (process/cell_cube.py)
         data/processed/geojson/NASA_SSH_<ENSO|IOD|PDO>_INDICATOR.geojson  (scripts/raw_to_json.py)
"""

from __future__ import annotations

import calendar
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

GEOJSON = ROOT / "data" / "processed" / "geojson"
INDICATORS = {
    "enso": "NASA_SSH_ENSO_INDICATOR",
    "iod": "NASA_SSH_IOD_INDICATOR",
    "pdo": "NASA_SSH_PDO_INDICATOR",
}


def month_span(first: str, last: str) -> list[str]:
    """Every month from first to last inclusive, as YYYYMM."""
    y, m = int(first[:4]), int(first[4:])
    end = int(last[:4]) * 12 + int(last[4:]) - 1
    out = []
    k = y * 12 + m - 1
    while k <= end:
        out.append(f"{k // 12:04d}{k % 12 + 1:02d}")
        k += 1
    return out


def align(periods: list[str], values: np.ndarray, target: list[str]) -> np.ndarray:
    """A series on the target months: NaN where the source has no value for that month."""
    lookup = dict(zip(periods, np.asarray(values, dtype=float).tolist(), strict=True))
    return np.array([lookup.get(p, np.nan) for p in target], dtype=float)


def days_per_month(target: list[str]) -> np.ndarray:
    return np.array([calendar.monthrange(int(p[:4]), int(p[4:]))[1] for p in target], dtype=float)


def indicator_monthly(name: str) -> dict[str, float]:
    """Monthly mean of a NASA-SSH indicator, keyed by YYYYMM. Empty if the file is missing."""
    key = INDICATORS[name]
    path = GEOJSON / f"{key}.geojson"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    sums: dict[str, list[float]] = {}
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        decimal = props.get("decimal_year")
        values = [v for k, v in props.items() if k != "decimal_year"]
        if decimal is None or not values or values[0] is None:
            continue
        year = int(decimal)
        month = min(int((decimal - year) * 12) + 1, 12)
        sums.setdefault(f"{year:04d}{month:02d}", []).append(float(values[0]))
    return {k: float(np.mean(v)) for k, v in sums.items()}


def indicator_series(name: str, target: list[str]) -> np.ndarray:
    monthly = indicator_monthly(name)
    if not monthly:
        return np.full(len(target), np.nan)
    periods = sorted(monthly)
    return align(periods, np.array([monthly[p] for p in periods]), target)
