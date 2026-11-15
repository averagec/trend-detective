"""City list for the flood and drought flow. Owns: reading and checking the user-supplied CSV.
Local file only.

Expected file: data/catalog/cities_idn.csv with the columns
    city_id, name, lat, lon, rainfall_source
  - lat, lon: decimal degrees (WGS84)
  - rainfall_source: the rainfall series used for this city, one of RAINFALL_SOURCES
city_id must be unique and stable, because the page sends it back.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COORDS = ROOT / "data" / "catalog" / "city_coordinates_idn.csv"  # city, lat, lon

REQUIRED = ("city_id", "name", "lat", "lon", "rainfall_source")
RAINFALL_SOURCES = {
    "merra2:precip": "MERRA-2 bias-corrected precipitation (PRECTOTCORR)",
    "gpcp:gpcp_precip": "GPCP v3.3 satellite and gauge precipitation",
}


@dataclass(frozen=True)
class City:
    city_id: str
    name: str
    lat: float
    lon: float
    rainfall_source: str


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _load_name_list(path: Path, coords_path: Path) -> list[City]:
    """A name-only list (city, region): coordinates come from coords_path (city, lat, lon)."""
    if not coords_path.exists():
        raise FileNotFoundError(
            f"{coords_path} not found: it gives the coordinates for {path.name}."
        )
    with open(coords_path, newline="", encoding="utf-8") as f:
        coords = {r["city"].strip(): (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}
    cities: list[City] = []
    seen: set[str] = set()
    with open(path, newline="", encoding="utf-8") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            name = (row["city"] or "").strip()
            if not name:
                raise ValueError(f"{path.name} line {n}: city is required")
            if name not in coords:
                raise ValueError(
                    f"{path.name} line {n}: no coordinates for {name!r} in {coords_path.name}"
                )
            city_id = _slug(name)
            if city_id in seen:
                raise ValueError(f"{path.name} line {n}: duplicate city {name!r}")
            seen.add(city_id)
            lat, lon = coords[name]
            cities.append(City(city_id, name, lat, lon, "merra2:precip"))
    return cities


def load_cities(path: Path, coords_path: Path = COORDS) -> list[City]:
    """Read the city list. Accepts the full CSV (city_id, name, lat, lon, rainfall_source) or a
    name-only list (city, region), whose coordinates come from coords_path."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Add the city list as a CSV with columns {', '.join(REQUIRED)}."
        )
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    if "city" in header and "city_id" not in header:
        return _load_name_list(path, Path(coords_path))
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
        cities: list[City] = []
        seen: set[str] = set()
        for n, row in enumerate(reader, start=2):
            city_id = (row["city_id"] or "").strip()
            name = (row["name"] or "").strip()
            source = (row["rainfall_source"] or "").strip()
            if not city_id or not name:
                raise ValueError(f"{path.name} line {n}: city_id and name are required")
            if city_id in seen:
                raise ValueError(f"{path.name} line {n}: duplicate city_id {city_id!r}")
            if source not in RAINFALL_SOURCES:
                raise ValueError(
                    f"{path.name} line {n}: rainfall_source must be one of "
                    f"{', '.join(sorted(RAINFALL_SOURCES))}"
                )
            try:
                lat, lon = float(row["lat"]), float(row["lon"])
            except (TypeError, ValueError) as err:
                raise ValueError(f"{path.name} line {n}: lat and lon must be numbers") from err
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"{path.name} line {n}: lat or lon out of range")
            seen.add(city_id)
            cities.append(City(city_id, name, lat, lon, source))
    return cities
