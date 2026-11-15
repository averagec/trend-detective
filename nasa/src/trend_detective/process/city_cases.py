"""One monthly series per study city, for the CASES flow. Pure functions over arrays: no I/O.

Owns: picking the MERRA-2 grid cell for a city (the nearest cell that has data) and cutting its
months to whole calendar years. No statistics: the series is handed to the analysis engine
(POST /api/lineup). The rule matches the TEMP and RAIN city series already in cases_data.json: one
grid cell, the nearest, never an average of cells.
"""

from __future__ import annotations

import math

import numpy as np

KM_PER_DEG = 111.195
MIN_MONTHS = 24  # the least the statistics accept (two years)
MAX_DISTANCE_KM = 150.0  # a city further than this from any cell with data gets no series


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def nearest_cell(
    values: np.ndarray, lats: np.ndarray, lons: np.ndarray, lat: float, lon: float
) -> tuple[int, int, float] | None:
    """(row, column, km) of the cell nearest to (lat, lon) with at least MIN_MONTHS months of data
    that lies within MAX_DISTANCE_KM, or None. `values` is months x lat x lon."""
    have = np.isfinite(values).sum(axis=0) >= MIN_MONTHS
    best: tuple[int, int, float] | None = None
    for i in range(lats.size):
        for j in range(lons.size):
            if not have[i, j]:
                continue
            d = distance_km(lat, lon, float(lats[i]), float(lons[j]))
            if d <= MAX_DISTANCE_KM and (best is None or d < best[2]):
                best = (i, j, d)
    return best


def calendar_years(
    series: np.ndarray, first_period: str, y0: int, y1: int
) -> list[float | None]:
    """The months of whole calendar years y0..y1 (January first), None where there is no value.
    `first_period` is the cube's first month as "YYYYMM"."""
    fy, fm = int(first_period[:4]), int(first_period[4:6])
    out: list[float | None] = []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            k = (y - fy) * 12 + (m - fm)
            v = series[k] if 0 <= k < series.size else np.nan
            out.append(None if not np.isfinite(v) else float(v))
    return out
