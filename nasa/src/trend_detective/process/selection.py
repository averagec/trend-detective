"""Selection engine: a city or circle becomes grid cells, then series and statistics.

Owns: the cell lookup for a city, the circle rule, the monthly timeline, the static cell mask, the
area average over a circle, and the cell agreement summary. No file reads, no network. Trends and
p-values come from core/ only (core.summary.summarise); this module only chooses and averages cells.

Rules (see docs/decisions/0005-spatial-selection.md):
  - A city maps to the one cell whose centre is nearest, which is the cell that contains it.
  - A circle includes every cell whose centre lies within the radius (great-circle distance).
  - The radius must be 75 to 250 km, and a circle must hold at least 4 cells.
  - A cell with no value in any month is dropped before anything is averaged, so the cell set
    is the same for every month.
  - Series are placed on a full monthly timeline with NaN for missing months, and must start in
    January (core.summary.summarise expects both).
  - A circle's headline is the spread between its cells. The area average is shown as a reference.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from trend_detective.core.summary import Summary, summarise
from trend_detective.core.trend import area_weighted_mean

RADIUS_MIN_KM = 75.0
RADIUS_MAX_KM = 250.0
MIN_CELLS = 4
EARTH_RADIUS_KM = 6371.0
KM_PER_DEG = 111.2


class SelectionError(ValueError):
    """The request cannot be answered: outside the grid, a bad radius, or too few cells."""


@dataclass(frozen=True)
class Grid:
    lat: np.ndarray  # cell-centre latitudes, as stored in the cube
    lon: np.ndarray  # cell-centre longitudes

    @property
    def dlat(self) -> float:
        return float(np.median(np.abs(np.diff(self.lat))))

    @property
    def dlon(self) -> float:
        return float(np.median(np.abs(np.diff(self.lon))))


@dataclass(frozen=True)
class Cell:
    i: int
    j: int
    lat: float
    lon: float
    height_km: float
    width_km: float


def make_cell(grid: Grid, i: int, j: int) -> Cell:
    lat = float(grid.lat[i])
    lon = float(grid.lon[j])
    return Cell(
        i=i,
        j=j,
        lat=lat,
        lon=lon,
        height_km=grid.dlat * KM_PER_DEG,
        width_km=grid.dlon * KM_PER_DEG * math.cos(math.radians(lat)),
    )


def city_cell(grid: Grid, lat: float, lon: float) -> Cell:
    """The single cell that contains the point."""
    i = int(np.argmin(np.abs(grid.lat - lat)))
    j = int(np.argmin(np.abs(grid.lon - lon)))
    if abs(grid.lat[i] - lat) > grid.dlat / 2 or abs(grid.lon[j] - lon) > grid.dlon / 2:
        raise SelectionError("the point is outside the grid")
    return make_cell(grid, i, j)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Works on scalars or numpy arrays."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlam = np.radians(np.asarray(lon2) - lon1)
    h = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))


def circle_cells(grid: Grid, lat: float, lon: float, radius_km: float) -> list[Cell]:
    """Every cell whose centre lies within radius_km of (lat, lon)."""
    if not RADIUS_MIN_KM <= radius_km <= RADIUS_MAX_KM:
        raise SelectionError(
            f"radius must be {RADIUS_MIN_KM:g} to {RADIUS_MAX_KM:g} km, got {radius_km:g}"
        )
    lat_grid, lon_grid = np.meshgrid(grid.lat, grid.lon, indexing="ij")
    dist = haversine_km(lat, lon, lat_grid, lon_grid)
    ii, jj = np.where(dist <= radius_km)
    if ii.size < MIN_CELLS:
        raise SelectionError(
            f"the circle holds {ii.size} cell(s); at least {MIN_CELLS} are needed"
        )
    return [make_cell(grid, int(i), int(j)) for i, j in zip(ii, jj, strict=True)]


def to_timeline(periods: list[str], values: np.ndarray) -> np.ndarray:
    """Place values (one row per period) on a full monthly timeline, NaN for missing months."""
    if not periods:
        raise SelectionError("no months in the series")
    if periods != sorted(periods) or len(set(periods)) != len(periods):
        raise SelectionError("periods must be unique and in order")
    if not periods[0].endswith("01"):
        raise SelectionError("a series must start in January")

    def month_number(period: str) -> int:
        return int(period[:4]) * 12 + int(period[4:]) - 1

    start = month_number(periods[0])
    idx = np.array([month_number(p) - start for p in periods])
    out = np.full((int(idx[-1]) + 1,) + values.shape[1:], np.nan)
    out[idx] = values
    return out


def timeline_periods(first: str, n: int) -> list[str]:
    year, month = int(first[:4]), int(first[4:])
    out = []
    for k in range(n):
        m = month - 1 + k
        out.append(f"{year + m // 12:04d}{m % 12 + 1:02d}")
    return out


def area_average(full: np.ndarray, lats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Cos-latitude weighted mean over the valid cells in each month, and the valid count."""
    n_months = full.shape[0]
    out = np.full(n_months, np.nan)
    n_valid = np.zeros(n_months, dtype=int)
    for t in range(n_months):
        ok = np.isfinite(full[t])
        n_valid[t] = int(ok.sum())
        if n_valid[t]:
            out[t] = area_weighted_mean(full[t, ok].reshape(-1, 1), lats[ok])
    return out, n_valid


@dataclass(frozen=True)
class CellTrend:
    lat: float
    lon: float
    summary: Summary

    @property
    def slope(self) -> float:
        return self.summary.ols_per_decade

    @property
    def rising(self) -> bool:
        return bool(self.summary.ols_significant and self.slope > 0)

    @property
    def falling(self) -> bool:
        return bool(self.summary.ols_significant and self.slope < 0)


@dataclass(frozen=True)
class CityResult:
    cell: Cell
    periods: list[str]
    series: np.ndarray
    summary: Summary
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CircleResult:
    radius_km: float
    cells_in_circle: int
    cells_used: int
    cells: tuple[CellTrend, ...]
    rising: int  # cells with a significant rising trend
    falling: int  # cells with a significant falling trend
    not_significant: int
    slope_min: float  # per decade, over cells with a finite slope
    slope_max: float
    periods: list[str]
    average: Summary  # reference: the area average of all used cells
    average_series: np.ndarray
    valid_per_month: np.ndarray
    warnings: tuple[str, ...]


def analyse_city(
    values: np.ndarray,
    periods: list[str],
    grid: Grid,
    lat: float,
    lon: float,
    unit: str,
    label: str,
    city_name: str,
) -> CityResult:
    """One city: the series of the cell that contains it, with a scale warning."""
    cell = city_cell(grid, lat, lon)
    full = to_timeline(periods, np.asarray(values[:, cell.i, cell.j], dtype=float))
    tl = timeline_periods(periods[0], full.size)
    summary = summarise(full, unit, label)
    warn = (
        f"This series is for one grid cell, {cell.width_km:.0f} × {cell.height_km:.0f} km, "
        f"centred at {cell.lat:.2f}, {cell.lon:.2f}. The cell includes {city_name} and its "
        "surroundings, so neighbouring cells may trend differently.",
    )
    return CityResult(cell, tl, full, summary, warn + summary.warnings)


def analyse_circle(
    values: np.ndarray,
    periods: list[str],
    grid: Grid,
    lat: float,
    lon: float,
    radius_km: float,
    unit: str,
    label: str,
) -> CircleResult:
    """A circle: every cell in it, each with its own trend, and the area average as reference."""
    cells = circle_cells(grid, lat, lon, radius_km)
    ii = np.array([c.i for c in cells])
    jj = np.array([c.j for c in cells])
    raw = np.asarray(values[:, ii, jj], dtype=float)  # (months, cells)
    full = to_timeline(periods, raw)
    tl = timeline_periods(periods[0], full.shape[0])

    keep = np.isfinite(full).any(axis=0)  # static mask: drop cells with no value in any month
    used = [c for c, k in zip(cells, keep, strict=True) if k]
    full = full[:, keep]
    if len(used) < MIN_CELLS:
        raise SelectionError(
            f"only {len(used)} cell(s) in the circle have data; at least {MIN_CELLS} are needed"
        )

    per_cell = tuple(
        CellTrend(c.lat, c.lon, summarise(full[:, k], unit, f"cell {c.lat:.2f}, {c.lon:.2f}"))
        for k, c in enumerate(used)
    )
    rising = sum(1 for t in per_cell if t.rising)
    falling = sum(1 for t in per_cell if t.falling)
    slopes = np.array([t.slope for t in per_cell], dtype=float)
    finite = slopes[np.isfinite(slopes)]
    avg, n_valid = area_average(full, np.array([c.lat for c in used]))
    average = summarise(avg, unit, label)

    warnings: list[str] = []
    if len(cells) != len(used):
        dropped = len(cells) - len(used)
        warnings.append(f"{dropped} cell(s) had no data in any month and were left out.")
    if rising and falling:
        warnings.append(
            f"Mixed signal: {rising} cell(s) rise and {falling} fall significantly. "
            "The average hides this; compare the cells."
        )

    return CircleResult(
        radius_km=radius_km,
        cells_in_circle=len(cells),
        cells_used=len(used),
        cells=per_cell,
        rising=rising,
        falling=falling,
        not_significant=len(per_cell) - rising - falling,
        slope_min=float(finite.min()) if finite.size else float("nan"),
        slope_max=float(finite.max()) if finite.size else float("nan"),
        periods=tl,
        average=average,
        average_series=avg,
        valid_per_month=n_valid,
        warnings=tuple(warnings) + average.warnings,
    )
