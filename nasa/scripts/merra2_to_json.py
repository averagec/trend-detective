"""Convert the downloaded MERRA-2 daily T2MMAX subsets (data/raw/merra2/) to GeoJSON, offline.

Owns: reading the Harmony subset files, applying the shared QC rules, writing GeoJSON.
The cleaning (fill and range masking) and the area-weighted mean are reused from
process/merra2_clean.py and core/trend.py, so nothing is recomputed ad hoc here.
Works on whatever has been downloaded so far; the output says how much that is.

Run from the nasa folder:
    python scripts/merra2_to_json.py

Outputs (RFC 7946, WGS84 lon/lat), in data/processed/geojson/:
    M2SDNXSLV_T2MMAX_SEA_DAILY.geojson    one Feature per daily file
    M2SDNXSLV_T2MMAX_SEA_MONTHLY.geojson  one Feature per COMPLETE month (mean of daily means)

Every Feature uses the Southeast Asia box as its Polygon, as the ocean GeoJSONs do. A month with
missing days (an interrupted download) is left out of the monthly file and listed under
"excluded" with the reason; nothing disappears silently.
"""

from __future__ import annotations

import calendar
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from raw_to_json import REGION  # noqa: E402  (the Southeast Asia box used by the ocean files)

from trend_detective.core.trend import area_weighted_mean  # noqa: E402
from trend_detective.process.merra2_clean import (  # noqa: E402
    SPECS,
    SUBSET,
    clean_field,
    index_files,
    new_qc,
    read_fields,
)

OUT = ROOT / "data" / "processed" / "geojson"
COLLECTION = "M2SDNXSLV"
SPEC = SPECS["t2mmax"]
POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [REGION["lon_min"], REGION["lat_min"]],
            [REGION["lon_max"], REGION["lat_min"]],
            [REGION["lon_max"], REGION["lat_max"]],
            [REGION["lon_min"], REGION["lat_max"]],
            [REGION["lon_min"], REGION["lat_min"]],
        ]
    ],
}


def header(name: str, extra: dict) -> dict:
    return {
        "type": "FeatureCollection",
        "dataset": name,
        "source": {
            "short_name": COLLECTION,
            "title": "MERRA-2 statD_2d_slv_Nx: 2D daily statistics, single-level diagnostics",
            "source": "NASA GES DISC via Harmony (spatial subset)",
            "downloaded_footprint_west_south_east_north": "60,-50,179.375,60",
            "converted_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "kind": "gridded",
        "variable": "T2MMAX: daily maximum 2 m air temperature",
        "units": SPEC.unit,
        "region": {**REGION, "cell_selection": "cell centres inside box"},
        "method": "cos(latitude)-weighted mean over valid cells; fill and out-of-range masked",
        **extra,
    }


def feature(props: dict) -> dict:
    return {"type": "Feature", "geometry": POLYGON, "properties": props}


def main() -> None:
    files = index_files(COLLECTION, 8)
    if not files:
        sys.exit(f"No {COLLECTION} files under {SUBSET}")
    qc = new_qc()
    daily: list[dict] = []
    excluded: list[dict] = []
    cell_valid = None
    for day, path in sorted(files.items()):
        try:
            lats, lons, raw = read_fields(path, [SPEC.merra])
        except (OSError, KeyError, ValueError) as err:
            excluded.append({"file": path.name, "reason": f"unreadable: {err}"})
            continue
        field = clean_field(SPEC, raw[SPEC.merra], qc)
        rows = (lats >= REGION["lat_min"]) & (lats <= REGION["lat_max"])
        cols = (lons >= REGION["lon_min"]) & (lons <= REGION["lon_max"])
        sub = field[np.ix_(rows, cols)]
        valid = int(np.isfinite(sub).sum())
        if valid == 0:
            excluded.append({"file": path.name, "reason": "no valid cells in region"})
            continue
        cell_valid = (
            np.isfinite(sub).astype(int) if cell_valid is None else cell_valid + np.isfinite(sub)
        )
        mean = area_weighted_mean(sub, lats[rows])
        daily.append(
            {
                "date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
                "area_weighted_mean_t2mmax_k": round(float(mean), 4),
                "valid_cells": valid,
                "total_cells": int(sub.size),
                "source_file": path.name,
            }
        )

    per_month: dict[str, list[float]] = defaultdict(list)
    for r in daily:
        per_month[r["date"][:7]].append(r["area_weighted_mean_t2mmax_k"])
    monthly: list[dict] = []
    for ym, values in sorted(per_month.items()):
        year, month = int(ym[:4]), int(ym[5:])
        expected = calendar.monthrange(year, month)[1]
        if len(values) != expected:
            excluded.append(
                {
                    "file": f"month {ym}",
                    "reason": f"incomplete month: {len(values)} of {expected} days",
                }
            )
            continue
        monthly.append(
            {
                "year_month": ym,
                "mean_of_daily_max_t2m_k": round(float(np.mean(values)), 4),
                "n_days": len(values),
            }
        )

    coverage = {
        "daily_files_read": len(files),
        "first_day": daily[0]["date"],
        "last_day": daily[-1]["date"],
        "complete_months": len(monthly),
        "first_complete_month": monthly[0]["year_month"] if monthly else None,
        "last_complete_month": monthly[-1]["year_month"] if monthly else None,
        "region_cells": int(daily[0]["total_cells"]),
        "cells_valid_every_day": int((cell_valid == len(daily)).sum()),
        "cells_never_valid": int((cell_valid == 0).sum()),
        "qc": qc,
        "note": "Partial: built from the files downloaded so far (see download.log).",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, key, recs in (
        ("M2SDNXSLV_T2MMAX_SEA_DAILY", "daily", daily),
        ("M2SDNXSLV_T2MMAX_SEA_MONTHLY", "monthly", monthly),
    ):
        doc = header(
            name,
            {
                "coverage": coverage,
                "counts": {"valid_records": len(recs), "excluded": len(excluded)},
                "excluded": excluded,
                "features": [feature(r) for r in recs],
            },
        )
        # Keep the member order readable: metadata first, features last.
        doc["features"] = doc.pop("features")
        (OUT / f"{name}.geojson").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {len(recs)} {key} features to {OUT / (name + '.geojson')}")
    print(json.dumps(coverage, indent=2))
    if excluded:
        print(
            f"{len(excluded)} excluded:",
            *[f"{e['file']}: {e['reason']}" for e in excluded],
            sep="\n  ",
        )


if __name__ == "__main__":
    main()
