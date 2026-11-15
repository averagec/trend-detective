"""Monthly sea-level series next to each coastal Indonesian city, from the ECCO 0.5 degree grid.

Owns: picking the ocean cells beside a city and averaging them, month by month. No trend
statistics here (those are in core/).

A city's series is the cos(latitude)-weighted mean of every valid ocean cell whose centre lies
within `MAX_KM` of the city (the same centre-inside rule as the circle mode, ADR 0005).
Cities further than `COAST_KM` from the coast are inland, and get no series: sea level does
not apply to them.
ECCO's land cells are NaN in the processed .npz files, so only ocean cells can be picked.

Inputs : data/processed/ocean_se_asia/ECCO_L4_SSH_05DEG_MONTHLY_V4R4_YYYY-MM.npz
         data/processed/indonesia/cities.csv   (scripts/build_indonesia_geo.py)
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from trend_detective.core.trend import area_weighted_mean

ROOT = Path(__file__).resolve().parents[3]
GRID_DIR = ROOT / "data" / "processed" / "ocean_se_asia"
CITIES = ROOT / "data" / "processed" / "indonesia" / "cities.csv"
PRODUCT = "ECCO_L4_SSH_05DEG_MONTHLY_V4R4"
NAME_RE = re.compile(PRODUCT + r"_(\d{4})-(\d{2})\.npz$")
COAST_KM = 20.0  # a city further than this from the sea is treated as inland
MAX_KM = 120.0  # ocean cell centres considered "next to" a city


@dataclass(frozen=True)
class City:
    name: str
    province: str
    lat: float
    lon: float
    population: int
    capital: bool
    coast_km: float
    region: str = ""

    @property
    def coastal(self) -> bool:
        return self.coast_km <= COAST_KM


def read_cities(path: Path = CITIES) -> list[City]:
    with path.open(newline="") as fh:
        return [
            City(
                r["name"],
                r["province"],
                float(r["lat"]),
                float(r["lon"]),
                int(r["population"]),
                r["capital"] == "True",
                float(r["coast_km"]),
                r.get("region", ""),
            )
            for r in csv.DictReader(fh)
        ]


def load_grid(folder: Path = GRID_DIR):
    """Return (first_year, lats, lons, ssh[month, lat, lon] in metres). Months start in January."""
    files = sorted(
        (m.groups(), p) for p in folder.glob(f"{PRODUCT}_*.npz") if (m := NAME_RE.search(p.name))
    )
    if not files:
        raise FileNotFoundError(f"no {PRODUCT} files in {folder}")
    first = files[0][1]
    with np.load(first) as d:
        lats, lons = d["lat"].astype(float), d["lon"].astype(float)
    y0, m0 = int(files[0][0][0]), int(files[0][0][1])
    y1, m1 = int(files[-1][0][0]), int(files[-1][0][1])
    if m0 != 1:
        raise ValueError(f"{PRODUCT} must start in January, starts {y0}-{m0:02d}")
    n = (y1 - y0) * 12 + m1
    ssh = np.full((n, lats.size, lons.size), np.nan)
    for (y, m), p in files:
        with np.load(p) as d:
            ssh[(int(y) - y0) * 12 + int(m) - 1] = d["ssh"]
    return y0, lats, lons, ssh


def km(lat1, lon1, lat2, lon2):
    k = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lon2 - lon1) * k, lat2 - lat1) * 111.32


def nearest_cells(city: City, lats, lons, ocean: np.ndarray) -> list[tuple[int, int, float]]:
    """Every ocean cell (row, col, distance km) whose centre is within MAX_KM, nearest first."""
    cand = []
    for i in np.where(np.abs(lats - city.lat) <= 1.5)[0]:
        for j in np.where(np.abs(lons - city.lon) <= 1.5)[0]:
            if ocean[i, j]:
                d = km(city.lat, city.lon, lats[i], lons[j])
                if d <= MAX_KM:
                    cand.append((int(i), int(j), d))
    return sorted(cand, key=lambda c: c[2])


def grid_around(city: City, lats, lons, ocean: np.ndarray, radius_km: float = MAX_KM):
    """Every grid cell that touches the circle: (row, col, centre distance km, is_ocean, inside).

    `inside` means the cell centre is within radius_km, so the cell can be used. Cells that only
    overlap the edge are listed so the map can draw the whole circle.
    """
    half_lat = float(abs(lats[1] - lats[0])) / 2
    half_lon = float(abs(lons[1] - lons[0])) / 2
    out = []
    for i in np.where(np.abs(lats - city.lat) <= 2.0)[0]:
        for j in np.where(np.abs(lons - city.lon) <= 2.0)[0]:
            near_lat = min(max(city.lat, lats[i] - half_lat), lats[i] + half_lat)
            near_lon = min(max(city.lon, lons[j] - half_lon), lons[j] + half_lon)
            if km(city.lat, city.lon, near_lat, near_lon) > radius_km:
                continue
            d = km(city.lat, city.lon, lats[i], lons[j])
            out.append((int(i), int(j), d, bool(ocean[i, j]), d <= radius_km))
    return sorted(out, key=lambda c: c[2])


def city_series(city: City, lats, ssh: np.ndarray, cells) -> np.ndarray:
    """Monthly sea level next to the city, in millimetres."""
    rows = np.array([c[0] for c in cells])
    cols = np.array([c[1] for c in cells])
    out = np.full(ssh.shape[0], np.nan)
    for t in range(ssh.shape[0]):
        vals = ssh[t, rows, cols]
        if np.isfinite(vals).any():
            out[t] = area_weighted_mean(vals[:, None], lats[rows]) * 1000.0
    return out
