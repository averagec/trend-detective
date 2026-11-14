"""Clean downloaded MERRA-2 subsets and build regional monthly series.

Owns: reading the Harmony subset files, QC masking, unit conversion, the derived VPD, and
area-weighted regional means. No trend statistics here: those live in core/trend.py.
Needs numpy and h5py only (no network).

Inputs : data/raw/merra2/subset/<collection>/<year>/*.nc4   (from ingest/merra2_download.py)
Outputs: data/processed/merra2/monthly_regional.csv   one row per region, variable and month
         data/processed/merra2/qc_report.json         what was masked, and why, per variable

Cleaning rules (see docs/statistics.md, section "Data cleaning"):
  1. Fill values (|x| >= 1e14; MERRA-2 uses 1e15) and NaNs are masked.
  2. Values outside a physical range (the Spec.valid column) are masked, not clipped.
  3. Units are converted: precipitation and evaporation kg m-2 s-1 -> mm day-1 (x 86400),
     specific humidity kg kg-1 -> g kg-1 (x 1000). Temperatures stay in K (a trend in K equals
     a trend in degC).
  4. Each month's grid is averaged over a region with cos(latitude) weights (core/trend.py).
  5. Daily T2MMAX is averaged over the region per day, then over the days of each month.
  6. VPD (kPa) is computed per grid cell from the monthly means of T2M, QV2M and PS.
     This is an approximation: the monthly mean of VPD is not the VPD of the monthly means.

Examples:
    python src/trend_detective/process/merra2_clean.py
    python src/trend_detective/process/merra2_clean.py --regions east_asia_land --variables t2m vpd
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.catalog.regions import REGIONS, Region  # noqa: E402
from trend_detective.core.trend import area_weighted_mean  # noqa: E402

SUBSET = ROOT / "data" / "raw" / "merra2" / "subset"
OUT = ROOT / "data" / "processed" / "merra2"
FILL_THRESHOLD = 1e14  # MERRA-2 fill value is 1e15
SECONDS_PER_DAY = 86400.0  # kg m-2 s-1 -> mm day-1 (1 kg of water per m2 is 1 mm)
EPSILON = 0.622  # ratio of molar masses of water and dry air
FILE_RE = re.compile(r"\.(\d{8}|\d{6})(?:_[A-Z0-9]+)?_subsetted\.nc4$")


@dataclass(frozen=True)
class Spec:
    key: str  # short output name
    merra: str  # MERRA-2 variable name
    collection: str
    unit: str  # unit after conversion
    scale: float  # raw value x scale = output value
    valid: tuple[float, float]  # plausible range in RAW units; outside is masked


SPECS: dict[str, Spec] = {
    "t2m": Spec("t2m", "T2M", "M2TMNXSLV", "K", 1.0, (180.0, 340.0)),
    "t2mmax": Spec("t2mmax", "T2MMAX", "M2SDNXSLV", "K", 1.0, (180.0, 345.0)),
    "qv2m": Spec("qv2m", "QV2M", "M2TMNXSLV", "g kg-1", 1000.0, (0.0, 0.05)),
    "ps": Spec("ps", "PS", "M2TMNXSLV", "Pa", 1.0, (30000.0, 110000.0)),
    "evap": Spec("evap", "EVAP", "M2TMNXFLX", "mm day-1", SECONDS_PER_DAY, (-0.001, 0.01)),
    "precip": Spec("precip", "PRECTOTCORR", "M2TMNXFLX", "mm day-1", SECONDS_PER_DAY, (0.0, 0.05)),
    "tsurf": Spec("tsurf", "TSURF", "M2TMNXLND", "K", 1.0, (180.0, 345.0)),
}
VPD_INPUTS = ("t2m", "qv2m", "ps")
ALL_VARIABLES = [*SPECS, "vpd"]
VPD_UNIT = "kPa"


def index_files(collection: str, key_len: int) -> dict[str, Path]:
    """Map period key (YYYYMM or YYYYMMDD) to the file for one collection."""
    out: dict[str, Path] = {}
    for path in sorted((SUBSET / collection).glob("*/*.nc4")):
        m = FILE_RE.search(path.name)
        if m and len(m.group(1)) == key_len:
            out[m.group(1)] = path
    return out


def clean_field(spec: Spec, raw: np.ndarray, qc: dict) -> np.ndarray:
    """Mask fill values and out-of-range cells, then convert units. Counts go into qc."""
    x = np.asarray(raw, dtype=float)
    fill = ~np.isfinite(x) | (np.abs(np.nan_to_num(x, nan=0.0)) >= FILL_THRESHOLD)
    lo, hi = spec.valid
    out_of_range = ~fill & ((x < lo) | (x > hi))
    qc["cells"] += x.size
    qc["fill_masked"] += int(fill.sum())
    qc["out_of_range_masked"] += int(out_of_range.sum())
    x = np.where(fill | out_of_range, np.nan, x)
    return x * spec.scale


def vpd_kpa(t_k: np.ndarray, qv_kgkg: np.ndarray, ps_pa: np.ndarray) -> np.ndarray:
    """Vapour pressure deficit in kPa, from temperature (K), specific humidity and pressure.

    Saturation vapour pressure: Tetens over water. Actual vapour pressure from the specific
    humidity: e = q P / (eps + (1 - eps) q). NaN in any input gives NaN out.
    """
    tc = t_k - 273.15
    es = 0.6108 * np.exp(17.27 * tc / (tc + 237.3))  # kPa
    e = qv_kgkg * ps_pa / (EPSILON + (1.0 - EPSILON) * qv_kgkg) / 1000.0  # kPa
    return np.maximum(es - e, 0.0)


def region_mean(field: np.ndarray, lats: np.ndarray, lons: np.ndarray, region: Region):
    """Area-weighted mean over the cells whose centres fall inside the region's box.

    Returns (value or NaN, cells in box, valid cells in box).
    """
    west, south, east, north = region.bbox
    li = np.where((lats >= south) & (lats <= north))[0]
    oi = np.where((lons >= west) & (lons <= east))[0]
    sub = field[np.ix_(li, oi)]
    n_valid = int(np.isfinite(sub).sum())
    if n_valid == 0:
        return float("nan"), int(sub.size), 0
    return area_weighted_mean(sub, lats[li]), int(sub.size), n_valid


def read_fields(path: Path, names: list[str]) -> tuple[np.ndarray, np.ndarray, dict]:
    """Lat, lon and the first time step of each named variable. Checks the variables exist."""
    with h5py.File(path, "r") as f:
        missing = [n for n in names if n not in f]
        if missing:
            raise KeyError(f"{path.name}: missing variables {missing}")
        lats = np.asarray(f["lat"][:], dtype=float)
        lons = np.asarray(f["lon"][:], dtype=float)
        raw = {n: np.asarray(f[n][0], dtype=float) for n in names}
    return lats, lons, raw


def new_qc() -> dict:
    return {"cells": 0, "fill_masked": 0, "out_of_range_masked": 0}


def monthly_rows(
    path: Path, period: str, wanted: list[str], regions: list[Region], qc: dict, rows: list
) -> None:
    """Regional monthly values for the requested variables from one monthly file."""
    names = [SPECS[k].merra for k in wanted]
    lats, lons, raw = read_fields(path, names)
    clean = {}
    for key in wanted:
        clean[key] = clean_field(SPECS[key], raw[SPECS[key].merra], qc.setdefault(key, new_qc()))
    if all(k in clean for k in VPD_INPUTS):
        t_k, qv_kg, ps_pa = clean["t2m"], clean["qv2m"] / 1000.0, clean["ps"]
        clean["vpd"] = vpd_kpa(t_k, qv_kg, ps_pa)
        qc.setdefault("vpd", new_qc())["cells"] += t_k.size
    for region in regions:
        for key, field in clean.items():
            value, n_cells, n_valid = region_mean(field, lats, lons, region)
            unit = VPD_UNIT if key == "vpd" else SPECS[key].unit
            rows.append(
                {
                    "region": region.key,
                    "variable": key,
                    "period": f"{period[:4]}-{period[4:6]}",
                    "value": value,
                    "unit": unit,
                    "n_cells": n_cells,
                    "n_valid": n_valid,
                    "n_days": "",
                }
            )


def daily_month_rows(daily: dict[str, Path], regions: list[Region], qc: dict, rows: list) -> None:
    """Monthly mean of the daily regional means of T2MMAX (one file per day)."""
    spec = SPECS["t2mmax"]
    per_month: dict[tuple[str, str], list[float]] = defaultdict(list)
    for day, path in sorted(daily.items()):
        lats, lons, raw = read_fields(path, [spec.merra])
        field = clean_field(spec, raw[spec.merra], qc.setdefault("t2mmax", new_qc()))
        for region in regions:
            value, _, _ = region_mean(field, lats, lons, region)
            if np.isfinite(value):
                per_month[(region.key, day[:6])].append(value)
    for (region_key, month), values in sorted(per_month.items()):
        rows.append(
            {
                "region": region_key,
                "variable": "t2mmax",
                "period": f"{month[:4]}-{month[4:6]}",
                "value": float(np.mean(values)),
                "unit": spec.unit,
                "n_cells": "",
                "n_valid": "",
                "n_days": len(values),
            }
        )


def build(regions: list[Region], variables: list[str]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    qc: dict = {}
    errors: list[str] = []
    counts = {}

    monthly_wanted = [k for k in variables if k in SPECS and SPECS[k].collection == "M2TMNXSLV"]
    if "vpd" in variables:
        monthly_wanted = sorted(set(monthly_wanted) | set(VPD_INPUTS))
    wanted_by_coll = {
        "M2TMNXSLV": monthly_wanted,
        "M2TMNXFLX": [k for k in variables if k in SPECS and SPECS[k].collection == "M2TMNXFLX"],
        "M2TMNXLND": [k for k in variables if k in SPECS and SPECS[k].collection == "M2TMNXLND"],
    }
    for coll, keys in wanted_by_coll.items():
        if not keys:
            continue
        files = index_files(coll, 6)
        counts[coll] = len(files)
        for period, path in sorted(files.items()):
            try:
                monthly_rows(path, period, keys, regions, qc, rows)
            except (KeyError, OSError, ValueError) as err:
                errors.append(f"{coll} {period}: {err}")

    if "t2mmax" in variables:
        daily = index_files("M2SDNXSLV", 8)
        counts["M2SDNXSLV"] = len(daily)
        try:
            daily_month_rows(daily, regions, qc, rows)
        except (KeyError, OSError, ValueError) as err:
            errors.append(f"M2SDNXSLV: {err}")

    # VPD needs T2M, QV2M and PS, so those rows are built too; keep only what was asked for.
    rows = [r for r in rows if r["variable"] in variables]
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_read": counts,
        "rows": len(rows),
        "errors": errors,
        "variables": qc,
    }
    return rows, report


def write_outputs(rows: list[dict], report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["region", "variable", "period", "value", "unit", "n_cells", "n_valid", "n_days"]
    rows = sorted(rows, key=lambda r: (r["region"], r["variable"], r["period"]))
    with open(out_dir / "monthly_regional.csv", "w", newline="", encoding="utf-8") as f:
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
    p.add_argument("--variables", nargs="+", choices=ALL_VARIABLES, default=ALL_VARIABLES)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    regions = [REGIONS[k] for k in args.regions]
    rows, report = build(regions, args.variables)
    write_outputs(rows, report, args.out)
    print(f"Wrote {len(rows)} rows to {args.out / 'monthly_regional.csv'}")
    if report["errors"]:
        print(f"{len(report['errors'])} files skipped, see qc_report.json")


if __name__ == "__main__":
    main()
