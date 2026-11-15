"""Turn your own GeoJSON study area into an AppEEARS area request (*-request.json).

Owns: validating a polygon GeoJSON and writing an AppEEARS area task body. Standard library
only. No network: the request is written to disk and you submit it yourself in AppEEARS.

Layout follows the AppEEARS sample area request (task_type, task_name, params with dates,
layers, geo and output). AppEEARS products are land and point products (MODIS, VIIRS, Landsat,
SMAP and so on). The ocean SSH data in data/processed/geojson is not in AppEEARS, so this
script is only for land products over your own area.

Example:
    python scripts/make_appeears_request.py my_area.geojson \\
        --task-name my_area_evi --start 02-18-2000 --end 12-31-2022 \\
        --product MOD13A1.061 --layer _500m_16_days_EVI --format geotiff --projection geographic

Writes docs/appeears/<task-name>-request.json unless --out is given.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "docs" / "appeears"
DATE_FORMAT = "%m-%d-%Y"
FORMATS = ("geotiff", "netcdf4")
TASK_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def fail(message: str) -> None:
    sys.exit(f"error: {message}")


def load_polygons(path: Path) -> dict:
    """Read a GeoJSON file and keep only its polygon features (no edits to the user's file)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        fail(f"cannot read {path}: {err}")
    if data.get("type") == "Feature":
        data = {"type": "FeatureCollection", "features": [data]}
    if data.get("type") != "FeatureCollection":
        fail("GeoJSON must be a FeatureCollection (or a single Feature)")
    features = []
    for i, feature in enumerate(data.get("features", []), start=1):
        geometry = feature.get("geometry") or {}
        kind = geometry.get("type")
        if kind not in ("Polygon", "MultiPolygon"):
            fail(f"feature {i} is {kind!r}; AppEEARS area requests need Polygon or MultiPolygon")
        polygons = [geometry["coordinates"]] if kind == "Polygon" else geometry["coordinates"]
        for polygon in polygons:
            for ring in polygon:
                check_ring(ring, i)
        features.append(
            {"type": "Feature", "properties": feature.get("properties") or {}, "geometry": geometry}
        )
    if not features:
        fail("the GeoJSON contains no features")
    return {"type": "FeatureCollection", "features": features}


def check_ring(ring: list, feature_no: int) -> None:
    if len(ring) < 4:
        fail(f"feature {feature_no} has a ring with fewer than 4 positions")
    if ring[0] != ring[-1]:
        fail(f"feature {feature_no} has a ring that is not closed (first and last must match)")
    for lon, lat in ring:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            fail(f"feature {feature_no} has a point outside lon/lat range: {lon}, {lat}")


def check_date(value: str, label: str) -> str:
    try:
        datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        fail(f"{label} must be MM-DD-YYYY, got {value!r}")
    return value


def build_request(args: argparse.Namespace, geo: dict) -> dict:
    start = check_date(args.start, "--start")
    end = check_date(args.end, "--end")
    if datetime.strptime(start, DATE_FORMAT) > datetime.strptime(end, DATE_FORMAT):
        fail("--start is after --end")
    date_entry: dict = {"startDate": start, "endDate": end, "recurring": args.recurring}
    if args.recurring:
        if not args.year_range:
            fail("--recurring needs --year-range START END")
        date_entry["yearRange"] = list(args.year_range)
    return {
        "task_type": "area",
        "task_name": args.task_name,
        "params": {
            "dates": [date_entry],
            "layers": [{"product": args.product, "layer": args.layer}],
            "geo": geo,
            "output": {
                "format": {"type": args.format, "filename_date": "calendar"},
                "projection": args.projection,
            },
        },
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("geojson", type=Path, help="your polygon GeoJSON file")
    p.add_argument("--task-name", required=True, help="letters, digits, '.', '_' or '-'")
    p.add_argument("--start", required=True, help="start date, MM-DD-YYYY")
    p.add_argument("--end", required=True, help="end date, MM-DD-YYYY")
    p.add_argument("--product", required=True, help="AppEEARS product, e.g. MOD13A1.061")
    p.add_argument("--layer", required=True, help="layer in that product, e.g. _500m_16_days_EVI")
    p.add_argument("--format", choices=FORMATS, default="geotiff")
    p.add_argument("--projection", default="geographic", help="e.g. geographic, native")
    p.add_argument("--recurring", action="store_true", help="repeat the date range every year")
    p.add_argument("--year-range", nargs=2, type=int, metavar=("START", "END"))
    p.add_argument("--out", type=Path, help="output path (default docs/appeears/<task>-request)")
    args = p.parse_args(argv)

    if not TASK_NAME.match(args.task_name):
        fail("--task-name may only contain letters, digits, '.', '_' and '-'")
    geo = load_polygons(args.geojson)
    request = build_request(args, geo)
    out = args.out or DEFAULT_OUT_DIR / f"{args.task_name}-request.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(geo['features'])} polygon feature(s))")


if __name__ == "__main__":
    main()
