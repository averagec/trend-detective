"""Per-cell cubes for the Indonesia box. One value per grid cell and month.

Owns: reading the monthly raw files cell by cell, applying the same QC and unit rules as the
regional cleaners (merra2_clean.py, witness_clean.py), and writing one compressed array per
variable. No trend statistics here. Needs numpy and h5py only (no network).

Datasets:
    merra2  MERRA-2 monthly collections, 0.625 x 0.5 degrees (about 69 x 55 km near Jakarta)
    gpcp    GPCP v3.3 monthly precipitation, grid spacing from the file (see the manifest)

Inputs : data/raw/merra2/subset/<collection>/<year>/*.nc4   (from ingest/merra2_download.py)
         data/raw/witness/gpcp/<year>/*.nc4                  (from ingest/witness_download.py)
Outputs: data/processed/cells/<dataset>_idn.npz           lat, lon, one array per variable shaped
                                                           (months, lat, lon), and <name>__periods
         data/processed/cells/<dataset>_idn_manifest.json  box, grid, QC counts and skipped files

A cell is kept when its centre lies inside BOX. Grid convention (checked against the raw files):
longitudes -180 + 0.625 k and latitudes -90 + 0.5 j for MERRA-2.

Examples:
    python src/trend_detective/process/cell_cube.py
    python src/trend_detective/process/cell_cube.py --datasets merra2 --variables t2m precip
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.process.merra2_clean import (  # noqa: E402
    SPECS,
    VPD_INPUTS,
    clean_field,
    index_files,
    new_qc,
    read_fields,
    vpd_kpa,
)
from trend_detective.process.witness_clean import SPECS as WITNESS_SPECS  # noqa: E402
from trend_detective.process.witness_clean import mask as witness_mask  # noqa: E402
from trend_detective.process.witness_clean import month_of_file, wrap_lon  # noqa: E402

OUT = ROOT / "data" / "processed" / "cells"
RAW_GPCP = ROOT / "data" / "raw" / "witness" / "gpcp"
BOX = (94.0, -12.0, 142.0, 7.0)  # west, south, east, north, in degrees; cell centres inside
CELL_VARIABLES = ["t2m", "qv2m", "ps", "precip", "evap", "tsurf", "vpd"]
COLLECTIONS = ["M2TMNXSLV", "M2TMNXFLX", "M2TMNXLND"]  # monthly collections only (T2MMAX later)
GPCP_SPEC = next(s for s in WITNESS_SPECS if s.var == "gpcp_precip")
VPD_UNIT = "kPa"
DATASETS = ["merra2", "gpcp"]


def box_slices(lats: np.ndarray, lons: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Indices of the rows and columns whose cell centres lie inside BOX."""
    li = np.where((lats >= BOX[1]) & (lats <= BOX[3]))[0]
    oi = np.where((lons >= BOX[0]) & (lons <= BOX[2]))[0]
    return li, oi


@dataclass
class Cube:
    lat: np.ndarray
    lon: np.ndarray
    values: dict[str, np.ndarray]  # variable -> (months, lat, lon), float32
    periods: dict[str, list[str]]  # variable -> ["YYYYMM", ...] aligned with the first axis
    manifest: dict


def build_merra2(variables: list[str] = CELL_VARIABLES) -> Cube:
    """Read every monthly MERRA-2 file once; clean each cell with merra2_clean's rules."""
    want = set(variables) | (set(VPD_INPUTS) if "vpd" in variables else set())
    store: dict[str, list[tuple[str, np.ndarray]]] = {k: [] for k in want}
    qc: dict = {}
    errors: list[str] = []
    files_read: dict[str, int] = {}
    lat = lon = None

    for coll in COLLECTIONS:
        keys = [k for k in want if k in SPECS and SPECS[k].collection == coll]
        if not keys:
            continue
        files = index_files(coll, 6)
        files_read[coll] = len(files)
        for period, path in sorted(files.items()):
            try:
                lats, lons, raw = read_fields(path, [SPECS[k].merra for k in keys])
            except (KeyError, OSError, ValueError) as err:
                errors.append(f"{coll} {period}: {err}")
                continue
            li, oi = box_slices(lats, lons)
            lat, lon = lats[li], lons[oi]
            clean = {}
            for k in keys:
                sub = raw[SPECS[k].merra][np.ix_(li, oi)]
                clean[k] = clean_field(SPECS[k], sub, qc.setdefault(k, new_qc()))
                store[k].append((period, clean[k]))
            if coll == "M2TMNXSLV" and "vpd" in want and all(k in clean for k in VPD_INPUTS):
                t_k, qv_kg, ps_pa = clean["t2m"], clean["qv2m"] / 1000.0, clean["ps"]
                store["vpd"].append((period, vpd_kpa(t_k, qv_kg, ps_pa)))

    manifest = {
        "dataset": "merra2",
        "cell_size_deg": {"lon": 0.625, "lat": 0.5},
        "files_read": files_read,
        "errors": errors,
        "units": {
            k: (VPD_UNIT if k == "vpd" else SPECS[k].unit)
            for k in variables
            if k in SPECS or k == "vpd"
        },
        "qc": qc,
    }
    return _finish(store, variables, lat, lon, manifest)


def build_gpcp() -> Cube:
    """Read every monthly GPCP file once; clean each cell with witness_clean's rules."""
    qc = {"cells": 0, "fill_masked": 0, "out_of_range_masked": 0}
    errors: list[str] = []
    steps: list[tuple[str, np.ndarray]] = []
    lat = lon = None
    files = sorted(RAW_GPCP.glob("*/*.nc4"))
    for path in files:
        month = month_of_file(path, GPCP_SPEC)
        if month is None:
            continue
        try:
            with h5py.File(path, "r") as f:
                lats = np.asarray(f["lat"][:], dtype=float)
                lons = wrap_lon(np.asarray(f["lon"][:], dtype=float))
                raw = np.asarray(f[GPCP_SPEC.source][0], dtype=float)
        except (KeyError, OSError, ValueError) as err:
            errors.append(f"{path.name}: {err}")
            continue
        li, oi = box_slices(lats, lons)
        lat, lon = lats[li], lons[oi]
        sub = raw[np.ix_(li, oi)]
        steps.append((month.replace("-", ""), witness_mask(sub, GPCP_SPEC, qc)))

    manifest = {
        "dataset": "gpcp",
        "files_read": {"gpcp": len(files)},
        "errors": errors,
        "units": {"gpcp_precip": GPCP_SPEC.unit},
        "qc": {"gpcp_precip": qc},
    }
    return _finish({"gpcp_precip": steps}, ["gpcp_precip"], lat, lon, manifest)


def _finish(store, variables, lat, lon, manifest) -> Cube:
    arrays: dict[str, np.ndarray] = {}
    periods: dict[str, list[str]] = {}
    for k in variables:
        series = sorted(store.get(k, []), key=lambda item: item[0])
        if not series:
            continue
        periods[k] = [p for p, _ in series]
        arrays[k] = np.stack([a for _, a in series]).astype(np.float32)
    manifest["generated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest["box_west_south_east_north"] = list(BOX)
    manifest["cell_centres"] = {
        "lat": int(lat.size) if lat is not None else 0,
        "lon": int(lon.size) if lon is not None else 0,
    }
    manifest["variables"] = {
        k: {
            "unit": manifest["units"].get(k, ""),
            "months": len(periods[k]),
            "first": periods[k][0],
            "last": periods[k][-1],
            "shape": list(arrays[k].shape),
        }
        for k in arrays
    }
    if lat is None:
        raise SystemExit(f"no {manifest['dataset']} files read; check the raw folder")
    return Cube(lat, lon, arrays, periods, manifest)


def write(cube: Cube, out_dir: Path = OUT) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{cube.manifest['dataset']}_idn"
    payload = {"lat": cube.lat, "lon": cube.lon}
    for k, arr in cube.values.items():
        payload[k] = arr
        payload[f"{k}__periods"] = np.array(cube.periods[k])
    path = out_dir / f"{name}.npz"
    np.savez_compressed(path, **payload)
    (out_dir / f"{name}_manifest.json").write_text(
        json.dumps(cube.manifest, indent=2), encoding="utf-8"
    )
    return path


def load(path: Path) -> Cube:
    with np.load(path) as z:
        names = [
            n for n in z.files if n not in ("lat", "lon") and not n.endswith("__periods")
        ]
        values = {n: z[n] for n in names}
        periods = {n: [str(p) for p in z[f"{n}__periods"]] for n in names}
        manifest_path = path.with_name(path.stem + "_manifest.json")
        manifest = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return Cube(np.asarray(z["lat"]), np.asarray(z["lon"]), values, periods, manifest)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--datasets", nargs="+", choices=DATASETS, default=DATASETS)
    p.add_argument("--variables", nargs="+", choices=CELL_VARIABLES, default=CELL_VARIABLES)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    for name in args.datasets:
        cube = build_merra2(args.variables) if name == "merra2" else build_gpcp()
        path = write(cube, args.out)
        grid = f"{cube.lat.size} x {cube.lon.size}"
        print(f"{name}: wrote {len(cube.values)} variable(s) on {grid} to {path}")
        if cube.manifest["errors"]:
            skipped = len(cube.manifest["errors"])
            print(f"{name}: {skipped} files skipped, see the manifest")


if __name__ == "__main__":
    main()
