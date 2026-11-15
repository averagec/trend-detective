"""Build the small processed files the Flask app reads, for one region and one variable.

Runs the existing steps once, in order, and writes nothing to data/raw/ except what the
downloader itself caches there (git-ignored):

  ingest   ingest/merra2_download.py   Harmony subsets -> data/raw/merra2/subset/   (network)
  clean    process/merra2_clean.py     QC, units, regional mean for THIS region and variable,
                                       merged into data/processed/merra2/monthly_regional.csv
                                       (other regions and variables in that file are kept)
  analyse  process/analyse_trends.py   static JSON export -> data/processed/json/
  demo     (this script)               copies the demo cases to data/demo/ so the app runs
                                       offline: monthly_regional.csv, json/, cases.json

No statistics here: the trend and the 95% band come from core/ via analyse_trends.build().
The ingest step is a big download (see docs/datasets.md), so it only runs with
--confirm-download, and is skipped when the raw files are already on disk.

Examples:
    # Check what would happen. Nothing is downloaded, read or written.
    python scripts/build_processed.py --region se_asia_maritime --variable t2m --dry-run
    # Rebuild one series from raw files already on disk, then refresh the demo copy
    python scripts/build_processed.py --region east_asia_land --variable precip
    # Refresh only the exports and the demo copy from the committed processed CSV
    python scripts/build_processed.py --region east_asia_land --variable t2m --steps analyse demo
    # Fetch the raw files first (large; needs EARTHDATA_USERNAME / EARTHDATA_PASSWORD in .env)
    python scripts/build_processed.py --region se_asia_maritime --variable evap --confirm-download

Run the app on the demo copy:
    python src/trend_detective/app/web.py --input data/demo/monthly_regional.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.catalog.regions import REGIONS  # noqa: E402
from trend_detective.catalog.variables import VARIABLES  # noqa: E402
from trend_detective.process import analyse_trends, merra2_clean  # noqa: E402

STEPS = ("ingest", "clean", "analyse", "demo")
COLUMNS = ["region", "variable", "period", "value", "unit", "n_cells", "n_valid", "n_days"]
APP_COLUMNS = {"region", "variable", "period", "value", "unit"}  # what analyse_trends.load reads

# Variable key -> request group in ingest/merra2_download.py (PS only comes with the VPD group).
INGEST_GROUP = {
    "t2m": "t2m_monthly_mean",
    "t2mmax": "t2m_daily_max",
    "qv2m": "humidity",
    "ps": "vpd",
    "vpd": "vpd",
    "evap": "evaporation",
    "precip": "rainfall",
    "tsurf": "land_temperature",
}

# PROPOSED demo cases: heat and rain in every region, so the compare view can show contrast.
# The team has not picked the demo cases yet (exec-plans/active/hackathon-48h.md, step 3):
# change this list, or pass --demo REGION:VARIABLE ..., when they do.
DEMO_VARIABLES = ("t2m", "precip")
DEMO_CASES = tuple((region, variable) for variable in DEMO_VARIABLES for region in sorted(REGIONS))


def parse_case(text: str) -> tuple[str, str]:
    region, _, variable = text.partition(":")
    if region not in REGIONS or variable not in INGEST_GROUP:
        raise argparse.ArgumentTypeError(f"{text!r}: use REGION:VARIABLE, e.g. east_asia_land:t2m")
    return region, variable


# ---------------------------------------------------------------- files


def read_rows(path: Path) -> list[dict]:
    """Rows of a monthly_regional.csv with the value as a float (NaN when empty)."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["value"] = float(row["value"]) if row["value"] else math.nan
    return rows


def write_rows(rows: list[dict], path: Path) -> None:
    """Write rows in the same format as process/merra2_clean.py (sorted, 6 significant digits)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: (r["region"], r["variable"], r["period"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in ordered:
            value = "" if not math.isfinite(r["value"]) else f"{r['value']:.6g}"
            writer.writerow({**r, "value": value})


def merge_rows(existing: list[dict], new: list[dict], region: str, variable: str) -> list[dict]:
    """Replace the (region, variable) rows of `existing` with `new`; keep everything else."""
    kept = [r for r in existing if not (r["region"] == region and r["variable"] == variable)]
    return kept + [r for r in new if r["region"] == region and r["variable"] == variable]


def merge_report(old: dict, new: dict, rows: int) -> dict:
    """Update qc_report.json for one variable, keeping the other variables' entries."""
    return {
        "generated_utc": new["generated_utc"],
        "files_read": {**old.get("files_read", {}), **new.get("files_read", {})},
        "rows": rows,
        "errors": new.get("errors", []),
        "variables": {**old.get("variables", {}), **new.get("variables", {})},
    }


# ---------------------------------------------------------------- checks


def raw_file_counts(variable: str) -> dict[str, int]:
    """Collection -> number of subset files on disk that this variable's clean step reads."""
    if variable == "vpd":
        collections = {"M2TMNXSLV": 6}
    else:
        spec = merra2_clean.SPECS[variable]
        collections = {spec.collection: 8 if variable == "t2mmax" else 6}
    return {c: len(merra2_clean.index_files(c, k)) for c, k in collections.items()}


def check_app_contract(csv_path: Path, cases: list[tuple[str, str]]) -> list[str]:
    """Problems that would stop the Flask app from reading `csv_path` (empty list = fine)."""
    if not csv_path.exists():
        return [f"{csv_path} does not exist"]
    with open(csv_path, newline="", encoding="utf-8") as f:
        header = set(csv.DictReader(f).fieldnames or [])
    problems = []
    if not APP_COLUMNS <= header:
        problems.append(f"{csv_path.name} is missing columns {sorted(APP_COLUMNS - header)}")
        return problems
    series = analyse_trends.load(csv_path)
    for region, variable in cases:
        if (region, variable) not in series:
            problems.append(f"no rows for {region} / {variable} in {csv_path.name}")
    for region, variable in series:
        if region not in REGIONS:
            problems.append(f"unknown region {region!r} (not in catalog/regions.py)")
        if variable not in VARIABLES:
            problems.append(f"variable {variable!r} is not in catalog/variables.py (app hides it)")
    return sorted(set(problems))


# ---------------------------------------------------------------- steps


def step_ingest(variable: str) -> None:
    """Real download of this variable's group (the caller has checked --confirm-download)."""
    from trend_detective.ingest import merra2_download  # imports harmony only when needed

    merra2_download.main(
        ["download", "--only", INGEST_GROUP[variable], "--workers", "2", "--confirm"]
    )


def step_clean(region: str, variable: str, csv_path: Path) -> tuple[int, dict]:
    new_rows, report = merra2_clean.build([REGIONS[region]], [variable])
    if not any(r["region"] == region and r["variable"] == variable for r in new_rows):
        raise SystemExit(f"error: the clean step produced no rows for {region} / {variable}")
    existing = read_rows(csv_path) if csv_path.exists() else []
    merged = merge_rows(existing, new_rows, region, variable)
    write_rows(merged, csv_path)
    qc_path = csv_path.with_name("qc_report.json")
    old = json.loads(qc_path.read_text(encoding="utf-8")) if qc_path.exists() else {}
    qc_path.write_text(
        json.dumps(merge_report(old, report, len(merged)), indent=2), encoding="utf-8"
    )
    return len(merged), report


def step_analyse(csv_path: Path, json_dir: Path) -> None:
    analyse_trends.main(["--input", str(csv_path), "--out", str(json_dir)])


def step_demo(
    csv_path: Path, demo_dir: Path, cases: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Copy the demo cases' rows to demo_dir and export their JSON. Returns the cases copied."""
    rows = read_rows(csv_path)
    present = {(r["region"], r["variable"]) for r in rows}
    copied = [c for c in cases if c in present]
    for missing in (c for c in cases if c not in present):
        print(f"warning: demo case {missing[0]} / {missing[1]} is not in {csv_path.name}: skipped")
    demo_rows = [r for r in rows if (r["region"], r["variable"]) in set(copied)]
    write_rows(demo_rows, demo_dir / "monthly_regional.csv")
    demo_csv = demo_dir / "monthly_regional.csv"
    analyse_trends.main(["--input", str(demo_csv), "--out", str(demo_dir / "json")])
    manifest = {
        "note": "Demo cases for the offline demo. Made by scripts/build_processed.py; do not edit.",
        "source": "data/processed/merra2/monthly_regional.csv",
        "app_input": "data/demo/monthly_regional.csv",
        "cases": [{"region": r, "variable": v} for r, v in sorted(copied)],
        "rows": len(demo_rows),
    }
    (demo_dir / "cases.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return copied


# ---------------------------------------------------------------- main


def plan(args: argparse.Namespace, csv_path: Path, json_dir: Path, demo_dir: Path) -> bool:
    """Print what a real run would do. Returns False if it could not run as given."""
    ok = True
    print(f"Plan for {args.region} / {args.variable} (dry run: nothing is run or written)")
    counts = raw_file_counts(args.variable)
    on_disk = sum(counts.values())
    if "ingest" in args.steps:
        group = INGEST_GROUP[args.variable]
        if on_disk:
            print(f"  ingest   skip: {on_disk} raw files already on disk {counts}")
        elif args.confirm_download:
            print(f"  ingest   would download group '{group}' with merra2_download.py (large)")
        else:
            print(f"  ingest   needs raw files for group '{group}': none on disk {counts}")
            print("           add --confirm-download to fetch them (see docs/datasets.md for size)")
    if "clean" in args.steps:
        have_raw = on_disk or ("ingest" in args.steps and args.confirm_download)
        if not have_raw:
            print("  clean    BLOCKED: no raw files on disk and no download requested")
            ok = False
        else:
            print(f"  clean    would build {args.region} / {args.variable}, merge into {csv_path}")
    if "analyse" in args.steps:
        print(f"  analyse  would write the static JSON export to {json_dir}")
    if "demo" in args.steps:
        print(f"  demo     would copy {len(args.demo)} demo cases to {demo_dir}:")
        for region, variable in args.demo:
            print(f"             {region} / {variable}")
    if csv_path.exists():
        problems = check_app_contract(csv_path, list(args.demo) if "demo" in args.steps else [])
        for p in problems:
            print(f"  CHECK    {p}")
        print(f"  check    {csv_path.name}: " + ("FAILED" if problems else "app can read it"))
        ok = ok and not problems
    elif "clean" not in args.steps:
        print(f"  CHECK    {csv_path} does not exist")
        ok = False
    return ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--region", required=True, choices=sorted(REGIONS))
    p.add_argument("--variable", required=True, choices=sorted(INGEST_GROUP))
    p.add_argument("--steps", nargs="+", choices=STEPS, default=list(STEPS), help="default: all")
    p.add_argument("--demo", nargs="+", type=parse_case, default=list(DEMO_CASES), metavar="R:V")
    p.add_argument("--confirm-download", action="store_true", help="allow the large ingest step")
    p.add_argument("--data-dir", type=Path, default=ROOT / "data", help="default: data/")
    p.add_argument("--dry-run", action="store_true", help="check and print the plan, run nothing")
    args = p.parse_args(argv)

    processed = args.data_dir / "processed"
    csv_path = processed / "merra2" / "monthly_regional.csv"
    json_dir, demo_dir = processed / "json", args.data_dir / "demo"
    steps = [s for s in STEPS if s in args.steps]
    args.steps = steps

    if args.dry_run:
        return 0 if plan(args, csv_path, json_dir, demo_dir) else 1

    if "ingest" in steps and not any(raw_file_counts(args.variable).values()):
        if not args.confirm_download:
            print("error: no raw files on disk. Rerun with --confirm-download to fetch them,")
            print("       or use --steps analyse demo to work from the processed CSV.")
            return 1
        step_ingest(args.variable)
    elif "ingest" in steps:
        print("ingest: raw files already on disk, skipped")
    if "clean" in steps:
        rows, report = step_clean(args.region, args.variable, csv_path)
        print(f"clean: {csv_path} now has {rows} rows ({len(report['errors'])} files skipped)")
    problems = check_app_contract(csv_path, list(args.demo) if "demo" in steps else [])
    if problems:
        print("error: the processed CSV does not match what the app reads:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    if "analyse" in steps:
        step_analyse(csv_path, json_dir)
    if "demo" in steps:
        copied = step_demo(csv_path, demo_dir, list(args.demo))
        print(f"demo: copied {len(copied)} cases to {demo_dir}")
    print(f"done {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
