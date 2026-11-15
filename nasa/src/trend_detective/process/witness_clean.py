"""Clean the witness datasets and build regional monthly series.

Datasets (downloaded by ingest/witness_download.py):
  gldas  GLDAS Noah 2.1 soil moisture (4 layers) and rainfall, 0.25 degree, 2000 onward
  gpcp   GPCP v3.3 combined satellite-gauge rainfall (sat_gauge_precip), 0.5 degree, 1983 onward
  grace  JPL GRACE/GRACE-FO mascon water storage (lwe_thickness, cm), 0.5 degree, one global file

Owns: fill-value masking, range checks, unit conversion, the box cut and the area-weighted regional
means. No trend statistics here: those live in core/trend.py.

How it is general: every dataset is one entry in SPECS (file layout, variable, fill value, valid
range, unit conversion). The masking, box cut and averaging are shared by all entries. A new dataset
needs one new entry, not new code. It must have 1-D lat/lon coordinates and a month for each file
(from the file name) or a time variable (the GRACE case).

Inputs : data/raw/witness/<key>/...   (from ingest/witness_download.py)
Outputs: data/processed/witness/witness_regional.csv   one row per dataset, region, variable, month
         data/processed/witness/qc_report.json         masked counts per variable

Examples:
    python src/trend_detective/process/witness_clean.py
    python src/trend_detective/process/witness_clean.py --datasets gpcp --regions se_asia_maritime
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.catalog.regions import REGIONS, Region  # noqa: E402
from trend_detective.core.trend import area_weighted_mean  # noqa: E402

RAW = ROOT / "data" / "raw" / "witness"
OUT = ROOT / "data" / "processed" / "witness"
SECONDS_PER_DAY = 86400.0
GRACE_EPOCH = date(2002, 1, 1)


@dataclass(frozen=True)
class Spec:
    dataset: str  # folder under data/raw/witness and the "dataset" column
    var: str  # output key, e.g. gldas_sm_0_10cm
    source: str  # variable name inside the file
    unit: str  # unit after conversion
    scale: float  # raw x scale = output
    valid: tuple[float, float]  # plausible range in RAW units; outside is masked
    fills: tuple[float, ...]  # fill values written by the producer
    files: str  # glob under RAW / dataset, one file per month (or one file for GRACE)
    period: str  # "name" (YYYYMM in the file name) or "time" (GRACE time variable)
    pattern: str = ""  # regex with group 1 = YYYYMM, when period == "name"


GLDAS_FILE = r"\.A(\d{6})\."
GPCP_FILE = r"_L3_(\d{6})_"

SPECS: list[Spec] = [
    Spec(
        "gldas",
        "gldas_sm_0_10cm",
        "SoilMoi0_10cm_inst",
        "kg m-2",
        1.0,
        (0.0, 1000.0),
        (-9999.0,),
        "gldas/*/*.nc4",
        "name",
        GLDAS_FILE,
    ),
    Spec(
        "gldas",
        "gldas_sm_10_40cm",
        "SoilMoi10_40cm_inst",
        "kg m-2",
        1.0,
        (0.0, 2000.0),
        (-9999.0,),
        "gldas/*/*.nc4",
        "name",
        GLDAS_FILE,
    ),
    Spec(
        "gldas",
        "gldas_sm_40_100cm",
        "SoilMoi40_100cm_inst",
        "kg m-2",
        1.0,
        (0.0, 3000.0),
        (-9999.0,),
        "gldas/*/*.nc4",
        "name",
        GLDAS_FILE,
    ),
    Spec(
        "gldas",
        "gldas_sm_100_200cm",
        "SoilMoi100_200cm_inst",
        "kg m-2",
        1.0,
        (0.0, 5000.0),
        (-9999.0,),
        "gldas/*/*.nc4",
        "name",
        GLDAS_FILE,
    ),
    Spec(
        "gldas",
        "gldas_rain",
        "Rainf_tavg",
        "mm day-1",
        SECONDS_PER_DAY,
        (0.0, 0.05),
        (-9999.0,),
        "gldas/*/*.nc4",
        "name",
        GLDAS_FILE,
    ),
    Spec(
        "gpcp",
        "gpcp_precip",
        "sat_gauge_precip",
        "mm day-1",
        1.0,
        (0.0, 100.0),
        (-99999.0,),
        "gpcp/*/*.nc4",
        "name",
        GPCP_FILE,
    ),
    Spec(
        "grace",
        "grace_lwe",
        "lwe_thickness",
        "cm",
        1.0,
        (-200.0, 200.0),
        (-99999.0,),
        "grace/all/*.nc",
        "time",
    ),
]


def month_of_file(path: Path, spec: Spec) -> str | None:
    m = re.search(spec.pattern, path.name)
    return f"{m.group(1)[:4]}-{m.group(1)[4:6]}" if m else None


def grace_months(times: np.ndarray) -> list[str]:
    """GRACE time is days since 2002-01-01 (mid-month). Map each step to YYYY-MM."""
    out = []
    for t in times:
        d = GRACE_EPOCH + timedelta(days=float(t))
        out.append(f"{d.year:04d}-{d.month:02d}")
    return out


def wrap_lon(lon: np.ndarray) -> np.ndarray:
    """Longitudes in [-180, 180), so boxes given as -180..180 match grids stored as 0..360."""
    return ((lon + 180.0) % 360.0) - 180.0


def mask(raw: np.ndarray, spec: Spec, qc: dict) -> np.ndarray:
    """Set fill and out-of-range values to NaN, then convert units. Counts go into qc."""
    x = np.asarray(raw, dtype=float)
    fill = ~np.isfinite(x)
    for f in spec.fills:
        fill |= np.isclose(x, f, rtol=0, atol=1e-3)
    fill |= np.abs(np.nan_to_num(x, nan=0.0)) >= 1e14  # any remaining producer fill
    lo, hi = spec.valid
    out_of_range = ~fill & ((x < lo) | (x > hi))
    qc["cells"] += x.size
    qc["fill_masked"] += int(fill.sum())
    qc["out_of_range_masked"] += int(out_of_range.sum())
    x = np.where(fill | out_of_range, np.nan, x)
    return x * spec.scale


def region_mean(field: np.ndarray, lats: np.ndarray, lons: np.ndarray, region: Region):
    """Area-weighted mean over the cells whose centres fall inside the region box.

    Returns (value or NaN, cells in box, valid cells in box). lons must be in [-180, 180).
    """
    west, south, east, north = region.bbox
    li = np.where((lats >= south) & (lats <= north))[0]
    oi = np.where((lons >= west) & (lons <= east))[0]
    sub = field[np.ix_(li, oi)]
    n_valid = int(np.isfinite(sub).sum())
    if n_valid == 0:
        return float("nan"), int(sub.size), 0
    return area_weighted_mean(sub, lats[li]), int(sub.size), n_valid


def read_grid(f: h5py.File, name: str) -> tuple[np.ndarray, np.ndarray]:
    lats = np.asarray(f["lat"][:], dtype=float)
    lons = wrap_lon(np.asarray(f["lon"][:], dtype=float))
    return lats, lons


def rows_for_spec(spec: Spec, regions: list[Region], qc: dict) -> list[dict]:
    """Regional monthly rows for one variable of one dataset."""
    files = sorted((RAW / spec.files.split("/")[0]).glob("/".join(spec.files.split("/")[1:])))
    rows: list[dict] = []
    counter = qc.setdefault(spec.var, {"cells": 0, "fill_masked": 0, "out_of_range_masked": 0})
    if not files:
        return rows

    if spec.period == "name":
        for path in files:
            period = month_of_file(path, spec)
            if period is None:
                continue
            with h5py.File(path, "r") as f:
                lats, lons = read_grid(f, spec.source)
                field = mask(np.asarray(f[spec.source][0], dtype=float), spec, counter)
            rows += _region_rows(spec, period, field, lats, lons, regions)
    else:  # GRACE: one file, time along the first axis
        path = files[0]
        with h5py.File(path, "r") as f:
            lats, lons = read_grid(f, spec.source)
            times = np.asarray(f["time"][:], dtype=float)
            months = grace_months(times)
            keep = grace_keep_steps(times, months)
            counter["duplicate_steps_dropped"] = len(months) - len(keep)
            ds = f[spec.source]
            for i in keep:
                field = mask(np.asarray(ds[i], dtype=float), spec, counter)
                rows += _region_rows(spec, months[i], field, lats, lons, regions)
    return rows


def grace_keep_steps(times: np.ndarray, months: list[str]) -> list[int]:
    """One time step per month. Where two steps fall in one month, keep the one nearest the 15th
    (the mid-month convention). Two months in the file have two steps (2012-01 and 2015-04)."""
    best: dict[str, tuple[float, int]] = {}
    for i, (t, period) in enumerate(zip(times, months, strict=True)):
        day = (GRACE_EPOCH + timedelta(days=float(t))).day
        dist = abs(day - 15)
        if period not in best or dist < best[period][0]:
            best[period] = (dist, i)
    return sorted(i for _, i in best.values())


def _region_rows(spec, period, field, lats, lons, regions) -> list[dict]:
    out = []
    for region in regions:
        value, n_cells, n_valid = region_mean(field, lats, lons, region)
        out.append(
            {
                "dataset": spec.dataset,
                "region": region.key,
                "variable": spec.var,
                "period": period,
                "value": value,
                "unit": spec.unit,
                "n_cells": n_cells,
                "n_valid": n_valid,
            }
        )
    return out


def build(specs: list[Spec], regions: list[Region]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    qc: dict = {}
    errors: list[str] = []
    for spec in specs:
        try:
            rows += rows_for_spec(spec, regions, qc)
        except (KeyError, OSError, ValueError) as err:
            errors.append(f"{spec.var}: {err}")
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(rows),
        "errors": errors,
        "variables": qc,
    }
    return rows, report


def write_outputs(rows: list[dict], report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["dataset", "region", "variable", "period", "value", "unit", "n_cells", "n_valid"]
    rows = sorted(rows, key=lambda r: (r["dataset"], r["variable"], r["region"], r["period"]))
    with open(out_dir / "witness_regional.csv", "w", newline="", encoding="utf-8") as f:
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
    datasets = sorted({s.dataset for s in SPECS})
    p.add_argument("--datasets", nargs="+", choices=datasets, default=datasets)
    p.add_argument("--regions", nargs="+", choices=sorted(REGIONS), default=sorted(REGIONS))
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    specs = [s for s in SPECS if s.dataset in args.datasets]
    regions = [REGIONS[k] for k in args.regions]
    rows, report = build(specs, regions)
    write_outputs(rows, report, args.out)
    print(f"Wrote {len(rows)} rows to {args.out / 'witness_regional.csv'}")
    if report["errors"]:
        print(f"{len(report['errors'])} variables had errors, see qc_report.json")


if __name__ == "__main__":
    main()
