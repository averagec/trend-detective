"""Convert the downloaded NASA ocean data (data/raw/ocean/) to JSON, keeping only valid data.

Owns: reading raw granules and indicator text files, validity filtering, writing JSON.
Regional means come from core/trend.py (area_weighted_mean), never computed here.
No network access. Needs h5py for the NetCDF4/HDF5 granules.

Run from the repo root:
    python scripts/raw_to_json.py

Output: data/processed/geojson/<dataset>.geojson, one GeoJSON FeatureCollection per dataset
folder that has a manifest.csv (RFC 7946, WGS84 lon/lat). Each valid record is one Feature.
Gridded records use the Southeast Asia box as their Polygon; indicator records have null
geometry because the indices are not tied to a location. Every rejected file is listed under
the collection's "excluded" member with the reason, so nothing disappears silently.

Validity rules:
- gridded (NetCDF): manifest status "ok", file present, size matches the manifest, HDF5
  signature, variable present, month in the file name agrees with the manifest time_start,
  and at least one valid (non-fill, finite) cell in the region.
- indicator (text): manifest status "ok", every data row has the expected number of
  columns, all values finite and not the fill value 9.96921e36.
- Fill values are removed before any average is taken.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_detective.core.trend import area_weighted_mean  # noqa: E402

RAW = ROOT / "data" / "raw" / "ocean"
OUT = ROOT / "data" / "processed" / "geojson"

FILL = 1.0e36  # PO.DAAC fill value is 9.96921e36
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
MONTH_IN_NAME = re.compile(r"_(\d{4})-(\d{2})_")

# Southeast Asia box, cell centres inside it. Matches data/processed/ocean_se_asia (78 x 92 cells).
REGION = {"name": "Southeast Asia", "lon_min": 95, "lon_max": 141, "lat_min": -11, "lat_max": 28}

# Columns of each indicator text file, after the decimal-year column.
INDICATOR_COLUMNS = {
    "NASA_SSH_ENSO_INDICATOR": ["enso_index"],
    "NASA_SSH_IOD_INDICATOR": ["iod_index"],
    "NASA_SSH_PDO_INDICATOR": ["pdo_index"],
    "NASA_SSH_GMSL_INDICATOR": ["gmsl_cm", "gmsl_smoothed_60day_cm"],
}


def read_manifest(folder: Path) -> list[dict[str, str]]:
    with open(folder / "manifest.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_provenance(folder: Path) -> dict:
    path = folder / "provenance.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def wrap_lon(lon: np.ndarray) -> np.ndarray:
    """Map longitudes to [-180, 180) so one box test works for either convention."""
    return ((lon + 180.0) % 360.0) - 180.0


def in_region(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    return (
        (lat >= REGION["lat_min"])
        & (lat <= REGION["lat_max"])
        & (lon >= REGION["lon_min"])
        & (lon <= REGION["lon_max"])
    )


def read_gridded_region(path: Path, grid: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (field, lats): SSH values inside the region with fill set to NaN, plus cell latitudes.

    Raises OSError, KeyError or ValueError for a file that cannot be read as expected.
    """
    with h5py.File(path, "r") as f:
        ssh = np.asarray(f["SSH"][0], dtype=float)
        if grid == "latlon":  # 0.5 degree grid: rows are latitude, columns are longitude
            lat = np.asarray(f["latitude"][:], dtype=float)
            lon = np.asarray(f["longitude"][:], dtype=float)
            rows = (lat >= REGION["lat_min"]) & (lat <= REGION["lat_max"])
            cols = (lon >= REGION["lon_min"]) & (lon <= REGION["lon_max"])
            field = ssh[np.ix_(rows, cols)]
            lats = lat[rows]
        else:  # llc90 native grid: 13 tiles of 90 x 90 cells, with per-cell coordinates
            lat = np.asarray(f["YC"][:], dtype=float)
            lon = wrap_lon(np.asarray(f["XC"][:], dtype=float))
            inside = in_region(lat, lon)
            field = ssh[inside].reshape(-1, 1)
            lats = lat[inside]
    field = np.where(np.abs(field) >= FILL, np.nan, field)
    return field, lats


def month_from_name(name: str) -> str | None:
    m = MONTH_IN_NAME.search(name)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def process_gridded(folder: Path, grid: str) -> dict:
    records: list[dict] = []
    excluded: list[dict] = []
    for row in read_manifest(folder):
        name = row["name"]
        path = folder / name
        ym = month_from_name(name)
        reason = None
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        magic = b""
        if exists:
            with path.open("rb") as f:
                magic = f.read(8)
        if row.get("status") != "ok":
            reason = f"manifest status is {row.get('status')!r}"
        elif not exists:
            reason = "file missing"
        elif size == 0:
            reason = "empty file"
        elif row.get("bytes") and size != int(row["bytes"]):
            reason = "size differs from manifest (partial download?)"
        elif magic != HDF5_MAGIC:
            reason = "not an HDF5/NetCDF4 file"
        elif ym is None:
            reason = "no YYYY-MM in file name"
        elif row.get("time_start", "")[:7] != ym:
            reason = f"file month {ym} disagrees with manifest time_start {row.get('time_start')}"
        else:
            try:
                field, lats = read_gridded_region(path, grid)
            except (OSError, KeyError, ValueError) as err:
                reason = f"unreadable: {err}"
            else:
                valid = int(np.isfinite(field).sum())
                if valid == 0:
                    reason = "no valid cells in region"
                else:
                    mean = area_weighted_mean(field, lats)
                    if not np.isfinite(mean):
                        reason = "regional mean is not finite"
                    else:
                        records.append(
                            {
                                "year_month": ym,
                                "area_weighted_mean_ssh_m": round(mean, 6),
                                "valid_cells": valid,
                                "total_cells": int(field.size),
                                "source_file": name,
                            }
                        )
                        continue
        excluded.append({"file": name, "reason": reason})
    records.sort(key=lambda r: r["year_month"])
    return {
        "kind": "gridded",
        "variable": "SSH: dynamic sea surface height anomaly (SSH)",
        "units": "m",
        "region": {**REGION, "cell_selection": "cell centres inside box"},
        "method": "cos(latitude)-weighted mean over valid cells; fill values removed",
        "records": records,
        "excluded": excluded,
    }


def process_indicator(folder: Path, short: str) -> dict:
    """Parse the current (undated) indicator file. Dated copies in the folder are not used here."""
    columns = INDICATOR_COLUMNS[short]
    name = f"{short}.txt"
    rows = {r["name"]: r for r in read_manifest(folder)}
    row = rows.get(name)
    records: list[dict] = []
    excluded: list[dict] = []
    if row is None or row.get("status") != "ok" or not (folder / name).exists():
        excluded.append({"file": name, "reason": "current file missing or not ok in manifest"})
    else:
        bad_rows = 0
        text = (folder / name).read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if not line.strip() or line.startswith("HDR"):
                continue
            parts = line.split()
            try:
                nums = [float(p) for p in parts]
            except ValueError:
                bad_rows += 1
                continue
            values = nums[1:]
            if len(nums) != len(columns) + 1 or not np.isfinite(nums[0]):
                bad_rows += 1
                continue
            if any((not np.isfinite(v)) or abs(v) >= FILL for v in values):
                bad_rows += 1
                continue
            record = {"decimal_year": round(nums[0], 7)}
            record.update({c: round(v, 6) for c, v in zip(columns, values, strict=True)})
            records.append(record)
        if bad_rows:
            excluded.append(
                {"file": name, "reason": f"{bad_rows} malformed or fill-value rows dropped"}
            )
    records.sort(key=lambda r: r["decimal_year"])
    superseded = sum(1 for n in rows if n != name)
    return {
        "kind": "time_series",
        "columns": columns,
        "time_column": "decimal_year (year + fraction of year)",
        "records": records,
        "excluded": excluded,
        "note": f"Uses the current file {name}. The {superseded} dated files in the folder are "
        "earlier snapshots of the same series and are not used.",
    }


def region_polygon() -> dict:
    """The Southeast Asia box as a GeoJSON Polygon, exterior ring counter-clockwise (RFC 7946)."""
    w, s = REGION["lon_min"], REGION["lat_min"]
    e, n = REGION["lon_max"], REGION["lat_max"]
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def to_geojson(doc: dict, geometry: dict | None) -> dict:
    """One Feature per valid record. Everything else in the document becomes a foreign member."""
    features = [
        {"type": "Feature", "geometry": geometry, "properties": record}
        for record in doc["records"]
    ]
    header = {k: v for k, v in doc.items() if k != "records"}
    return {"type": "FeatureCollection", **header, "features": features}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for folder in sorted(p for p in RAW.iterdir() if p.is_dir()):
        if not (folder / "manifest.csv").exists():
            print(f"skip {folder.name}: no manifest.csv (download incomplete, nothing validated)")
            continue
        short = folder.name
        if short in INDICATOR_COLUMNS:
            doc = process_indicator(folder, short)
        else:
            grid = "llc" if "LLC" in short else "latlon"
            doc = process_gridded(folder, grid)
        doc = {"dataset": short, "source": read_provenance(folder), **doc}
        doc["counts"] = {
            "valid_records": len(doc["records"]),
            "excluded": len(doc["excluded"]),
        }
        geometry = region_polygon() if doc["kind"] == "gridded" else None
        out_path = OUT / f"{short}.geojson"
        geojson = to_geojson(doc, geometry)
        out_path.write_text(json.dumps(geojson, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        span = (
            f"{doc['records'][0].get('year_month', doc['records'][0].get('decimal_year'))} to "
            f"{doc['records'][-1].get('year_month', doc['records'][-1].get('decimal_year'))}"
            if doc["records"]
            else "no valid records"
        )
        print(
            f"{short}: {doc['counts']['valid_records']} valid, "
            f"{doc['counts']['excluded']} excluded ({span}) -> {out_path.relative_to(ROOT)}"
        )


if __name__ == "__main__":
    main()
