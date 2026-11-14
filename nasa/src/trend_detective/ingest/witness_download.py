"""Download three 'witness' datasets to check MERRA-2 against observations and other data.

  gldas  GLDAS Noah 2.1 monthly soil moisture (GLDAS_NOAH025_M), 0.25 degree, from 2000.
  gpcp   GPCP monthly rainfall v3.3 (GPCPMON), observed, from 1983. A second witness for rainfall.
  grace  JPL GRACE / GRACE-FO mascon water storage (RL06.3 V04), from 2002. Coarse, large regions.

Owns: CMR discovery, Harmony subsetting to the Asia-Pacific box and the listed variables, the
manifest. No statistics here. Downloads need EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env.

Variable names were checked against downloaded files (GLDAS 2000, GPCP 1983, GRACE). A wrong
name makes the Harmony job fail, and the manifest records why. The GRACE request does not cut the
box: Harmony returned the whole global file.

Commands (from the project root):
    python src/trend_detective/ingest/witness_download.py plan
    python src/trend_detective/ingest/witness_download.py download --confirm
    python src/trend_detective/ingest/witness_download.py download --confirm --only gldas:2000
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import traceback
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from harmony import BBox, Client, Collection, Request  # noqa: E402

from trend_detective.ingest.merra2_download import (  # noqa: E402
    is_hdf5,
    load_env,
    make_client,
    wait_and_resume,
)

CMR = "https://cmr.earthdata.nasa.gov"
UA = {"User-Agent": "trend-detective-witness/0.1"}
OUT = ROOT / "data" / "raw" / "witness"
# west, south, east, north. Same Asia-Pacific box as MERRA-2. East is 179.0 so every grid
# product here (0.25, 0.5 and about 0.5 degree cells) is cut inside the grid.
BOX = (60.0, -50.0, 179.0, 60.0)
# Share of the globe inside BOX, cos-latitude weighted. Used only to estimate sizes in the plan.
BOX_FRACTION = ((179.0 - 60.0) / 360.0) * ((0.8660 + 0.7660) / 2.0)
DONE_MARKER = ".done.json"


@dataclass(frozen=True)
class Witness:
    key: str
    short_name: str
    concept: str  # CMR concept ID (checked on CMR, see docs/data-sources.md)
    start: date
    end: date | None  # None = still updated: use today
    variables: tuple[str, ...]
    chunk: str  # "year" for one job per calendar year, "all" for one job for the whole record
    note: str


WITNESSES: dict[str, Witness] = {
    "gldas": Witness(
        key="gldas",
        short_name="GLDAS_NOAH025_M",
        concept="C1342986036-GES_DISC",
        start=date(2000, 1, 1),
        end=None,
        variables=(
            "SoilMoi0_10cm_inst",
            "SoilMoi10_40cm_inst",
            "SoilMoi40_100cm_inst",
            "SoilMoi100_200cm_inst",
            "Rainf_tavg",
        ),
        chunk="year",
        note="GLDAS Noah 2.1, monthly, 0.25 degree. Soil moisture by layer (kg m-2).",
    ),
    "gpcp": Witness(
        key="gpcp",
        short_name="GPCPMON",
        concept="C3405935516-GES_DISC",
        start=date(1983, 1, 1),
        end=date(2025, 12, 31),
        variables=("sat_gauge_precip",),  # combined satellite-gauge rainfall, mm/day
        chunk="year",
        note="GPCP monthly v3.3, 0.5 degree grid (not 2.5). Fill -99999. Do not use gauge_precip: "
        "it holds values below the fill value.",
    ),
    "grace": Witness(
        key="grace",
        short_name="TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4",
        concept="C3195502222-POCLOUD",
        start=date(2002, 4, 1),
        end=None,
        variables=(),  # the file is global and small (39 MB); the box is cut later in cleaning
        chunk="all",
        note="GRACE mascon, JPL RL06.3 V04, 0.5 degree grid. Whole file, global, with "
        "lwe_thickness (cm) and uncertainty. Fill -99999.",
    ),
}


def get_json(url: str, tries: int = 3) -> dict:
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)
        except OSError:
            if attempt == tries:
                raise
    raise RuntimeError("unreachable")


def cmr_granules(w: Witness, start: date, end: date) -> list[dict]:
    """Granule entries (time span and size) of one collection, from CMR."""
    params = [
        ("concept_id", w.concept),
        ("temporal", f"{start.isoformat()}T00:00:00Z,{end.isoformat()}T23:59:59Z"),
        ("page_size", "2000"),
    ]
    feed = get_json(f"{CMR}/search/granules.json?{urllib.parse.urlencode(params)}")
    return feed["feed"]["entry"]


def spans_of(entries: list[dict]) -> list[tuple[date, date, float]]:
    """(first day, last day, size in MB) for each granule."""
    out = []
    for e in entries:
        first = date.fromisoformat(e["time_start"][:10])
        last = date.fromisoformat(e["time_end"][:10])
        out.append((first, last, float(e.get("granule_size", 0.0))))
    return out


def window(w: Witness) -> tuple[date, date]:
    return w.start, (w.end or date.today())


def chunks(w: Witness, spans: list[tuple[date, date, float]]) -> list[tuple[str, date, date, int]]:
    """(label, first day, last day, expected files) for one dataset."""
    start, end = window(w)
    if w.chunk == "all":
        return [("all", start, end, len(spans))]
    out = []
    for year in range(start.year, end.year + 1):
        lo, hi = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
        expected = sum(1 for first, last, _ in spans if first <= hi and last >= lo)
        if expected:
            out.append((str(year), lo, hi, expected))
    return out


def plan_rows() -> list[dict]:
    rows = []
    for w in WITNESSES.values():
        start, end = window(w)
        spans = spans_of(cmr_granules(w, start, end))
        whole_mb = sum(mb for _, _, mb in spans)
        rows.append(
            {
                "dataset": w.key,
                "short_name": w.short_name,
                "granules": len(spans),
                "first": min((f for f, _, _ in spans), default=""),
                "last": max((last for _, last, _ in spans), default=""),
                "whole_files_mb": round(whole_mb, 1),
                "box_estimate_mb": round(whole_mb * BOX_FRACTION, 1),
                "variables": " ".join(w.variables),
                "harmony_jobs": len(chunks(w, spans)),
                "note": w.note,
            }
        )
    return rows


def cmd_plan(_: argparse.Namespace) -> None:
    rows = plan_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "plan.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    total_whole = sum(r["whole_files_mb"] for r in rows)
    total_box = sum(r["box_estimate_mb"] for r in rows)
    for r in rows:
        print(
            f"{r['dataset']:6} {r['short_name']}: {r['granules']} granules, "
            f"{r['first']} to {r['last']}, whole {r['whole_files_mb']} MB, "
            f"box ~{r['box_estimate_mb']} MB, {r['harmony_jobs']} Harmony jobs"
        )
        print(f"       variables: {r['variables']}")
        print(f"       {r['note']}")
    print(f"Total: whole files {total_whole / 1000:.2f} GB, box estimate {total_box / 1000:.2f} GB")
    print(f"Plan written to {OUT / 'plan.csv'}. Nothing downloaded.")


def run_chunk(
    env: dict[str, str], w: Witness, label: str, lo: date, hi: date, expected: int
) -> dict:
    """One Harmony job. Never raises: the error goes in the returned row."""
    outdir = OUT / w.key / label
    marker = outdir / DONE_MARKER
    row = {"dataset": w.key, "chunk": label, "expected": expected, "files": 0, "job_id": ""}
    if marker.exists():
        return {**row, "status": "skipped"}
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        client: Client = make_client(env, validate=False)
        west, south, east, north = BOX
        extra = {"variables": list(w.variables)} if w.variables else {}  # empty list breaks harmony
        request = Request(
            collection=Collection(id=w.concept),
            spatial=BBox(west, south, east, north),
            temporal={
                "start": datetime(lo.year, lo.month, lo.day),
                "stop": datetime(hi.year, hi.month, hi.day, 23, 59, 59),
            },
            format="application/x-netcdf4",
            **extra,
        )
        job_id = client.submit(request)
        row["job_id"] = job_id
        state = wait_and_resume(client, job_id)
        if state == "failed":
            return {**row, "status": "failed: Harmony job failed"}
        paths = [
            Path(str(fut.result())) for fut in client.download_all(job_id, directory=str(outdir))
        ]
        row["files"] = len(paths)
        bad = [p.name for p in paths if not is_hdf5(p)]
        if bad:
            return {**row, "status": f"failed: {len(bad)} outputs are not netCDF-4"}
        if len(paths) != expected:
            return {**row, "status": f"failed: got {len(paths)} files, CMR has {expected}"}
        marker.write_text(json.dumps({"job_id": job_id, "files": len(paths)}), encoding="utf-8")
        return {**row, "status": "ok"}
    except Exception as err:  # noqa: BLE001 - recorded in the manifest, other jobs carry on
        traceback.print_exc()
        return {**row, "status": f"failed: {err!r}"[:200]}


def cmd_download(args: argparse.Namespace) -> None:
    if not args.confirm:
        sys.exit("Refusing to download without --confirm. Run `plan` first and check the sizes.")
    env = load_env()
    only = dict(part.split(":", 1) if ":" in part else (part, None) for part in args.only)
    jobs = []
    for w in WITNESSES.values():
        if only and w.key not in only:
            continue
        start, end = window(w)
        spans = spans_of(cmr_granules(w, start, end))
        for label, lo, hi, expected in chunks(w, spans):
            if only.get(w.key) not in (None, "") and only[w.key] != label:
                continue
            jobs.append((w, label, lo, hi, expected))
    print(f"{len(jobs)} Harmony jobs, {args.workers} at a time")
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_chunk, env, w, label, lo, hi, n) for w, label, lo, hi, n in jobs]
        for done, fut in enumerate(as_completed(futures), start=1):
            row = fut.result()
            rows.append(row)
            print(f"[{done}/{len(jobs)}] {row['status']:8} {row['dataset']} {row['chunk']}")
    OUT.mkdir(parents=True, exist_ok=True)
    # Keep rows from earlier runs (for chunks not run this time) and replace the ones just run.
    fields = ["dataset", "chunk", "expected", "files", "job_id", "status"]
    manifest = OUT / "manifest.csv"
    kept = {}
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            kept = {(r["dataset"], r["chunk"]): r for r in csv.DictReader(f)}
    for r in rows:
        key = (r["dataset"], r["chunk"])
        if r["status"] == "skipped" and key in kept:
            continue  # already done in an earlier run: keep its original record
        kept[key] = r
    rows = list(kept.values())
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["dataset"], r["chunk"])))
    failed = [r for r in rows if r["status"].startswith("failed")]
    ok = len(rows) - len(failed)
    print(f"Done: {ok} ok or skipped, {len(failed)} failed. See {OUT / 'manifest.csv'}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Dry run: CMR counts and size estimates. No download.")
    d = sub.add_parser("download", help="Download the subsets (needs --confirm).")
    d.add_argument("--confirm", action="store_true", help="Actually download.")
    d.add_argument("--workers", type=int, default=2)
    d.add_argument(
        "--only",
        nargs="*",
        default=[],
        help="Limit to a dataset or one chunk, e.g. gldas:2000 gpcp",
    )
    args = p.parse_args(argv)
    if args.command == "plan":
        cmd_plan(args)
    else:
        cmd_download(args)


if __name__ == "__main__":
    main()
