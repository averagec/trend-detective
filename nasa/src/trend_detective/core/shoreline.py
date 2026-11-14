"""Shoreline position from SAR backscatter. Pure numpy: no I/O, no network.

Owns: water/land mask (Otsu on dB backscatter), shoreline position along a crop, a gap-limited
monthly series, and the trend analysis (via core/trend.py: stats come only from there).

Convention: positions are metres measured from the landward edge of the crop, so a
POSITIVE trend means the coast is growing seaward and a NEGATIVE trend means retreat.
The crop must contain the whole shoreline (land on one side, open sea on `sea_side`).
Known limitation: tide level changes the waterline between acquisitions (see tech debt).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .trend import TrendResult, deseasonalize, mann_kendall, ols_trend

MIN_YEARS = 10


def otsu_threshold(db: np.ndarray, bins: int = 256) -> float:
    """Threshold separating dark (water) from bright (land) pixels in a dB image."""
    v = db[np.isfinite(db)].ravel()
    hist, edges = np.histogram(v, bins=bins)
    p = hist / hist.sum()
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(p)
    m = np.cumsum(p * centers)
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (m[-1] * w0 - m) ** 2 / (w0 * (1 - w0))
    return float(centers[int(np.nanargmax(between))])


def water_mask(db: np.ndarray, threshold: float | None = None) -> np.ndarray:
    """True where water (low backscatter). Threshold defaults to Otsu on this image."""
    t = otsu_threshold(db) if threshold is None else threshold
    return db < t


def _sea_to_east(mask: np.ndarray, sea_side: str) -> np.ndarray:
    if sea_side == "east":
        return mask
    if sea_side == "west":
        return mask[:, ::-1]
    if sea_side == "north":
        return np.rot90(mask, k=-1)
    if sea_side == "south":
        return np.rot90(mask, k=1)
    raise ValueError(f"sea_side must be east/west/north/south, got {sea_side!r}")


def shoreline_position_m(
    mask: np.ndarray, pixel_m: float, sea_side: str = "east", min_run: int = 3
) -> float:
    """Median shoreline position (m from the landward edge) across all scan lines.

    Scanning inland from the sea edge, the shoreline is where a run of `min_run` land pixels
    starts; shorter land specks (boats, speckle) are ignored.
    """
    m = _sea_to_east(np.asarray(mask, dtype=bool), sea_side)
    width = m.shape[1]
    pos = np.empty(m.shape[0])
    for i, row in enumerate(m):
        land_run = 0
        boundary = 0  # all-water row: boundary at landward edge
        for j in range(width - 1, -1, -1):
            land_run = 0 if row[j] else land_run + 1
            if land_run >= min_run:
                boundary = j + min_run  # first pixel seaward of the land run
                break
        pos[i] = boundary
    return float(np.median(pos) * pixel_m)


def month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def monthly_series(idx: np.ndarray, values: np.ndarray, max_gap: int = 2) -> tuple[np.ndarray, int]:
    """Median per calendar month, consecutive from first to last month.

    Gaps of up to `max_gap` months are linearly interpolated; longer gaps raise ValueError
    (a series with big holes must not be passed to the trend tests). Returns (series, first_idx).
    """
    idx = np.asarray(idx, dtype=int)
    values = np.asarray(values, dtype=float)
    first, last = idx.min(), idx.max()
    out = np.full(last - first + 1, np.nan)
    for k in np.unique(idx):
        out[k - first] = np.median(values[idx == k])
    nan = np.isnan(out)
    run = 0
    for bad in nan:
        run = run + 1 if bad else 0
        if run > max_gap:
            raise ValueError(f"gap longer than {max_gap} months in the series")
    if nan.any():
        x = np.arange(out.size)
        out[nan] = np.interp(x[nan], x[~nan], out[~nan])
    return out, int(first)


@dataclass(frozen=True)
class ShorelineChange:
    ols: TrendResult
    mk: TrendResult
    m_per_decade: float  # OLS slope x 120 (months per decade)
    n_months: int
    warnings: list[str] = field(default_factory=list)


def analyze_shoreline(series_m: np.ndarray) -> ShorelineChange:
    """Deseasonalise, then OLS (autocorr-adjusted CI) + Mann-Kendall, per docs/science-rules.md."""
    anomalies = deseasonalize(np.asarray(series_m, dtype=float))
    ols = ols_trend(anomalies)
    mk = mann_kendall(anomalies)
    warns = []
    if len(series_m) < MIN_YEARS * 12:
        warns.append(
            f"Record is under {MIN_YEARS} years: a non-significant result may just need"
            " a longer record."
        )
    return ShorelineChange(ols, mk, ols.slope * 120, len(series_m), warns)
