"""GDIS flood and drought events as yearly counts per grid cell, 1980 to 2018.

Owns: reading the GDIS disaster-location CSV (inside its zip), keeping floods and droughts in the
project window, placing each record on the MERRA-2 cell grid of the Indonesia box, and writing the
counts. Counting only: no trend statistics here (those come from core/counts.py).

Inputs : data/raw/human_dimensions/gdis/pend-gdis-1960-2018-disasterlocations-csv.zip
         data/processed/cells/merra2_idn.npz  (lat, lon of the cells; process/cell_cube.py)
Outputs (committed, data/processed/gdis/):
         gdis_events_1980_2018.csv      one row per placed flood or drought record, with its cell
         gdis_yearly_counts_idn.csv     one row per year and cell with any event
         gdis_counts_idn.npz            the same counts as arrays, for the engine
         gdis_counts_idn_manifest.json  what was read, kept and placed

Each record is placed on the nearest cell centre, and only if it lies within half a cell of that
centre. GDIS locations are mostly administrative level 1 (regions), so a count is an approximate
location, not the exact place of the event.

Examples:
    python src/trend_detective/process/gdis.py
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ZIP = (
    ROOT
    / "data"
    / "raw"
    / "human_dimensions"
    / "gdis"
    / "pend-gdis-1960-2018-disasterlocations-csv.zip"
)
CELLS = ROOT / "data" / "processed" / "cells" / "merra2_idn.npz"
OUT = ROOT / "data" / "processed" / "gdis" / "gdis_counts_idn.npz"
HAZARDS = ("flood", "drought")
FIRST_YEAR, LAST_YEAR = 1980, 2018  # the project window (catalog/scope.py)


def read_events(path: Path = ZIP):
    """Yield one dict per record with a usable year and location."""
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        reader = csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace"))
        for row in reader:
            try:
                year = int(float(row["year"]))
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (TypeError, ValueError, KeyError):
                continue
            if not (math.isfinite(lat) and math.isfinite(lon)):
                continue
            yield {
                "year": year,
                "hazard": (row.get("disastertype") or "").strip().lower(),
                "country": row.get("country", ""),
                "adm1": row.get("adm1", ""),
                "latitude": lat,
                "longitude": lon,
            }


def count_events(
    events,
    lat: np.ndarray,
    lon: np.ndarray,
    first: int = FIRST_YEAR,
    last: int = LAST_YEAR,
    placed: list | None = None,
):
    """Yearly counts per cell for floods and droughts. Returns (years, {hazard: counts}, stats).

    If `placed` is a list, each placed record is appended to it with its cell centre.
    """
    years = np.arange(first, last + 1)
    counts = {h: np.zeros((years.size, lat.size, lon.size), dtype=np.int32) for h in HAZARDS}
    dlat = float(np.median(np.abs(np.diff(lat))))
    dlon = float(np.median(np.abs(np.diff(lon))))
    stats = {"read": 0, "in_scope": 0, "placed": 0, "outside_box": 0}
    for ev in events:
        stats["read"] += 1
        year, hazard = ev["year"], ev["hazard"]
        if hazard not in counts or not (first <= year <= last):
            continue
        stats["in_scope"] += 1
        la, lo = ev["latitude"], ev["longitude"]
        i = int(np.argmin(np.abs(lat - la)))
        j = int(np.argmin(np.abs(lon - lo)))
        if abs(lat[i] - la) > dlat / 2 or abs(lon[j] - lo) > dlon / 2:
            stats["outside_box"] += 1
            continue
        counts[hazard][year - first, i, j] += 1
        stats["placed"] += 1
        if placed is not None:
            placed.append({**ev, "cell_lat": float(lat[i]), "cell_lon": float(lon[j])})
    return years, counts, stats


def write_csv(out_dir: Path, years, counts: dict, placed: list[dict], lat, lon) -> dict:
    """The two CSV files for the repository."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "gdis_events_1980_2018.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["year", "hazard", "country", "adm1", "latitude", "longitude", "cell_lat", "cell_lon"]
        )
        for r in placed:
            w.writerow(
                [
                    r["year"],
                    r["hazard"],
                    r["country"],
                    r["adm1"],
                    r["latitude"],
                    r["longitude"],
                    r["cell_lat"],
                    r["cell_lon"],
                ]
            )
    rows = 0
    with open(out_dir / "gdis_yearly_counts_idn.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "cell_lat", "cell_lon", "flood", "drought"])
        for yi, year in enumerate(years):
            for i in range(lat.size):
                for j in range(lon.size):
                    fl, dr = int(counts["flood"][yi, i, j]), int(counts["drought"][yi, i, j])
                    if fl or dr:
                        w.writerow([int(year), float(lat[i]), float(lon[j]), fl, dr])
                        rows += 1
    return {"events_csv_rows": len(placed), "yearly_counts_csv_rows": rows}


def build(out: Path = OUT) -> dict:
    cells = np.load(CELLS)
    lat, lon = np.asarray(cells["lat"]), np.asarray(cells["lon"])
    placed: list[dict] = []
    years, counts, stats = count_events(read_events(), lat, lon, placed=placed)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, lat=lat, lon=lon, years=years, **counts)
    csv_stats = write_csv(out.parent, years, counts, placed, lat, lon)
    manifest = {
        "source": "GDIS 1960-2018, disaster locations (SEDAC)",
        "window": [FIRST_YEAR, LAST_YEAR],
        "cells": [int(lat.size), int(lon.size)],
        "hazards": list(HAZARDS),
        **stats,
        **csv_stats,
    }
    out.with_name(out.stem + "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    ).parse_args(argv)
    print(json.dumps(build(), indent=2))


if __name__ == "__main__":
    main()
