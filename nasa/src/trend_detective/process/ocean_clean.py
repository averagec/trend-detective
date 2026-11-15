"""Clean ECCO sea surface height into regional monthly rows, for four ECCO products.

  0.5 degree lat-lon grid (V4R4, V4R4B)   regular grid, 360 x 720 cells
  native LLC90 grid (V4R4, V4R4B)         13 tiles of 90 x 90 cells, with per-cell lat/lon

Owns: fill-value masking, range checks, the region box cut and area-weighted regional means, in
the same form as process/merra2_clean.py and process/witness_clean.py. No trend statistics here.

The LLC90 grid is curvilinear, so each cell has its own latitude. Its cells are treated as a
list (one cell per row), and the box cut uses each cell's centre. The weighting still goes through
core/trend.py area_weighted_mean, which gives each cell a cos(latitude) weight.

Missing values: ECCO writes land cells as 9.96921e+36. Those are masked, and so are values outside
the plausible range (-5 to 5 m). Regional means are over ocean cells only, so a region that includes
land (east_asia_land) averages its sea cells only. North Asia has no ocean cells, so its
value is blank.

Inputs : data/raw/ocean/ECCO_L4_SSH_*_MONTHLY_V4R4{,B}/*.nc   (from ingest/ocean_download.py)
Outputs: data/processed/ocean/ocean_regional.csv   one row per product, region and month
         data/processed/ocean/qc_report.json        masked counts per product

Examples:
    python src/trend_detective/process/ocean_clean.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.catalog.regions import REGIONS, Region  # noqa: E402
from trend_detective.core.trend import area_weighted_mean  # noqa: E402
from trend_detective.process.witness_clean import region_mean  # noqa: E402

RAW = ROOT / "data" / "raw" / "ocean"
OUT = ROOT / "data" / "processed" / "ocean"
# name in the output -> (folder under data/raw/ocean, grid)
VERSIONS = {
    "ecco_v4r4_05deg": ("ECCO_L4_SSH_05DEG_MONTHLY_V4R4", "latlon"),
    "ecco_v4r4b_05deg": ("ECCO_L4_SSH_05DEG_MONTHLY_V4R4B", "latlon"),
    "ecco_v4r4_llc90": ("ECCO_L4_SSH_LLC0090GRID_MONTHLY_V4R4", "llc"),
    "ecco_v4r4b_llc90": ("ECCO_L4_SSH_LLC0090GRID_MONTHLY_V4R4B", "llc"),
}
VAR = "SSH"
UNIT = "m"
VALID = (-5.0, 5.0)  # plausible sea surface height anomaly, metres
FILL_THRESHOLD = 1e30  # ECCO fill is 9.96921e+36
NAME_RE = re.compile(r"mon_mean_(\d{4})-(\d{2})_")


def clean(values: np.ndarray, qc: dict) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    fill = ~np.isfinite(x) | (np.abs(np.nan_to_num(x, nan=0.0)) >= FILL_THRESHOLD)
    lo, hi = VALID
    out_of_range = ~fill & ((x < lo) | (x > hi))
    qc["cells"] += x.size
    qc["fill_masked"] += int(fill.sum())
    qc["out_of_range_masked"] += int(out_of_range.sum())
    return np.where(fill | out_of_range, np.nan, x)


def read_month(path: Path, grid: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cell latitudes, longitudes and SSH for one month, as flat arrays (one value per cell)."""
    with h5py.File(path, "r") as f:
        if grid == "latlon":
            lats = np.asarray(f["latitude"][:], dtype=float)
            lons = np.asarray(f["longitude"][:], dtype=float)
            return lats, lons, np.asarray(f[VAR][0], dtype=float)
        # LLC90: per-cell centres, shape (13 tiles, 90, 90); the field has an extra time axis
        lats = np.asarray(f["YC"][:], dtype=float).ravel()
        lons = np.asarray(f["XC"][:], dtype=float).ravel()
        return lats, lons, np.asarray(f[VAR][0], dtype=float).ravel()


def cell_region_mean(field: np.ndarray, lats: np.ndarray, lons: np.ndarray, region: Region):
    """Area-weighted mean over the cells whose centres fall inside the box (curvilinear grid).

    The cells are passed to core/trend.area_weighted_mean as a column, so each cell is weighted by
    cos(its latitude). Returns (value or NaN, cells in box, valid cells in box).
    """
    west, south, east, north = region.bbox
    inside = (lats >= south) & (lats <= north) & (lons >= west) & (lons <= east)
    sub = field[inside]
    valid = np.isfinite(sub)
    n_cells, n_valid = int(inside.sum()), int(valid.sum())
    if n_valid == 0:
        return float("nan"), n_cells, 0
    value = area_weighted_mean(sub.reshape(-1, 1), lats[inside])
    return value, n_cells, n_valid


def build(regions: list[Region]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    report: dict = {"versions": {}, "errors": []}
    for dataset, (folder, grid) in VERSIONS.items():
        files = sorted((RAW / folder).glob("*.nc"))
        qc = {"files": 0, "cells": 0, "fill_masked": 0, "out_of_range_masked": 0}
        for path in files:
            m = NAME_RE.search(path.name)
            if not m:
                report["errors"].append(f"{path.name}: no year-month in name")
                continue
            period = f"{m.group(1)}-{m.group(2)}"
            try:
                lats, lons, raw = read_month(path, grid)
            except (KeyError, OSError, ValueError) as err:
                report["errors"].append(f"{path.name}: {err}")
                continue
            field = clean(raw, qc)
            qc["files"] += 1
            for region in regions:
                if grid == "latlon":
                    value, n_cells, n_valid = region_mean(
                        field.reshape(lats.size, lons.size), lats, lons, region
                    )
                else:
                    value, n_cells, n_valid = cell_region_mean(field, lats, lons, region)
                rows.append(
                    {
                        "dataset": dataset,
                        "region": region.key,
                        "variable": "ssh",
                        "period": period,
                        "value": value,
                        "unit": UNIT,
                        "n_cells": n_cells,
                        "n_valid": n_valid,
                    }
                )
        report["versions"][dataset] = qc
    report["generated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report["rows"] = len(rows)
    return rows, report


def write_outputs(rows: list[dict], report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["dataset", "region", "variable", "period", "value", "unit", "n_cells", "n_valid"]
    rows = sorted(rows, key=lambda r: (r["dataset"], r["region"], r["period"]))
    with open(out_dir / "ocean_regional.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in rows:
            value = r["value"]
            writer.writerow({**r, "value": "" if not np.isfinite(value) else f"{value:.6g}"})
    (out_dir / "qc_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--regions", nargs="+", choices=sorted(REGIONS), default=sorted(REGIONS))
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    regions = [REGIONS[k] for k in args.regions]
    rows, report = build(regions)
    write_outputs(rows, report, args.out)
    print(f"Wrote {len(rows)} rows to {args.out / 'ocean_regional.csv'}")
    if report["errors"]:
        print(f"{len(report['errors'])} files had errors, see qc_report.json")


if __name__ == "__main__":
    main()
