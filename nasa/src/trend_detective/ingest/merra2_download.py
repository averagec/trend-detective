"""Download MERRA-2 subsets for the trend-detective variables, over the Asia-Pacific box.

Owns: MERRA-2 request definitions, CMR discovery, Harmony subset jobs, manifests.
No analysis here. Needs harmony-py (declared in pyproject.toml).

Variables (Harmony cuts each granule down to these variables and the box; no whole files):
    t2m_monthly_mean   T2M        2 m air temperature, monthly mean          M2TMNXSLV
    t2m_daily_max      T2MMAX     2 m air temperature, daily maximum        M2SDNXSLV
    humidity           QV2M       2 m specific humidity, monthly mean        M2TMNXSLV
    vpd                T2M, QV2M, PS  inputs only: VPD is derived, not a MERRA-2 variable
    evaporation        EVAP       surface evaporation, monthly mean          M2TMNXFLX
    rainfall           PRECTOTCORR total precipitation (bias corrected), monthly M2TMNXFLX
    land_temperature   TSURF      land surface temperature incl. snow, monthly M2TMNXLND

Examples:
    # 1. Dry run (`plan`): CMR lookup and size estimate, writes a file list, no Harmony jobs
    python src/trend_detective/ingest/merra2_download.py plan
    # 2. Real run, only after the plan has been approved
    python src/trend_detective/ingest/merra2_download.py download --confirm --workers 2
    # Narrow it: --only t2m_daily_max rainfall   --start 2000-01-01 --end 2020-12-31
    #            --bbox 60,-50,180,60 (west,south,east,north; default is the Asia-Pacific box)

Credentials: EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env, never in code.
The CMR search needs no login. Harmony jobs do.
Jobs: one per collection and year, except the daily collection (M2SDNXSLV), which is one per
month because a whole year of daily granules made Harmony pause jobs partway through.
Writes data/raw/merra2/ (git-ignored): plan.csv (dry run), subset/<collection>/<year>/*.nc4,
manifest.csv, provenance.json. Re-runs skip chunks that finished (marked .done.json or
.done-MM.json).
"""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from harmony import BBox, Client, Collection, Request

ROOT = Path(__file__).resolve().parents[3]
CMR = "https://cmr.earthdata.nasa.gov"
PROVIDER = "GES_DISC"
VERSION = "5.12.4"
FIRST_DATE = date(1980, 1, 1)  # MERRA-2 starts 1980-01-01
DATA_DIR = ROOT / "data" / "raw" / "merra2"
UA = {"User-Agent": "trend-detective-merra2/0.1"}
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"  # netCDF-4 files are HDF5; an HTML error page fails this check
CMR_PAGE = (
    2000  # CMR page-number paging stops at 10,000 results, so discovery goes one year at a time
)
# west, south, east, north (Asia-Pacific box). East is 179.375, the grid's last longitude:
# with 180.0 Harmony ignored the longitude subset in the 2000 test.
DEFAULT_BBOX = (60.0, -50.0, 179.375, 60.0)
LON_STEP, LAT_STEP = 0.625, 0.5  # MERRA-2 grid spacing in degrees
BYTES_PER_VALUE = 4  # float32
DAILY_COLLECTIONS = {"M2SDNXSLV"}  # daily statistics: one Harmony job per month, not per year
POLL_SECONDS = 20
DONE_STATES = {"successful", "complete_with_errors", "failed", "canceled"}  # Harmony job states
MAX_WAIT_SECONDS = 6 * 3600

# Request groups. Groups that share a collection share its subset files (downloaded once).
GROUPS: dict[str, dict] = {
    "t2m_monthly_mean": {
        "collection": "M2TMNXSLV",
        "variables": ["T2M"],
        "frequency": "monthly mean",
    },
    "t2m_daily_max": {"collection": "M2SDNXSLV", "variables": ["T2MMAX"], "frequency": "daily max"},
    "humidity": {"collection": "M2TMNXSLV", "variables": ["QV2M"], "frequency": "monthly mean"},
    "vpd": {
        "collection": "M2TMNXSLV",
        "variables": ["T2M", "QV2M", "PS"],
        "frequency": "monthly mean (inputs; VPD is derived)",
    },
    "evaporation": {"collection": "M2TMNXFLX", "variables": ["EVAP"], "frequency": "monthly mean"},
    "rainfall": {
        "collection": "M2TMNXFLX",
        "variables": ["PRECTOTCORR"],
        "frequency": "monthly mean",
    },
    "land_temperature": {
        "collection": "M2TMNXLND",
        "variables": ["TSURF"],
        "frequency": "monthly mean",
    },
}


@dataclass
class Granule:
    collection: str
    name: str
    time_start: str
    groups: frozenset[str]


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    """Parse KEY=VALUE lines from .env. Lines without '=' are ignored."""
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip("'\"")
    return env


def get_json(url: str, tries: int = 3) -> dict:
    """Public CMR call with a few retries for transient network errors."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError):
            if attempt == tries:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError("unreachable")


def concept_id(collection: str) -> str:
    """CMR concept ID of a MERRA-2 collection, needed by Harmony."""
    params = [("short_name", collection), ("version", VERSION), ("provider", PROVIDER)]
    entries = get_json(f"{CMR}/search/collections.json?{urllib.parse.urlencode(params)}")
    entries = entries["feed"]["entry"]
    if not entries:
        sys.exit(f"CMR has no collection {collection} version {VERSION} from {PROVIDER}.")
    return entries[0]["id"]


def list_year(collection: str, year: int, start: date, end: date) -> list[dict]:
    """All CMR granule entries of one collection in one calendar year, clipped to start..end."""
    lo, hi = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
    if lo > hi:
        return []
    entries: list[dict] = []
    page = 1
    while True:
        params = [
            ("short_name", collection),
            ("version", VERSION),
            ("provider", PROVIDER),
            ("temporal", f"{lo.isoformat()}T00:00:00Z,{hi.isoformat()}T23:59:59Z"),
            ("page_size", str(CMR_PAGE)),
            ("page_num", str(page)),
        ]
        batch = get_json(f"{CMR}/search/granules.json?{urllib.parse.urlencode(params)}")
        batch = batch["feed"]["entry"]
        entries.extend(batch)
        if len(batch) < CMR_PAGE:
            return entries
        page += 1


def granule_name(entry: dict) -> str | None:
    """File name of a granule, taken from its HTTPS data link (metadata and S3 links skipped)."""
    for link in entry.get("links", []):
        href = link.get("href", "")
        if link.get("rel", "").endswith("data#") and href.startswith("https://"):
            return Path(urllib.parse.urlparse(href).path).name
    return None


def discover(
    collections: dict[str, frozenset[str]], start: date, end: date, workers: int
) -> list[Granule]:
    """CMR lookup for every (collection, year) pair, run in parallel. Returns unique granules."""
    found: dict[tuple[str, str], Granule] = {}
    jobs = [(c, y) for c in collections for y in range(start.year, end.year + 1)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(list_year, c, y, start, end): c for c, y in jobs}
        for fut in as_completed(futures):
            collection = futures[fut]
            for entry in fut.result():
                name = granule_name(entry)
                if name and (collection, name) not in found:
                    found[(collection, name)] = Granule(
                        collection=collection,
                        name=name,
                        time_start=entry.get("time_start", ""),
                        groups=collections[collection],
                    )
    return sorted(found.values(), key=lambda g: (g.collection, g.name))


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = (float(x) for x in text.split(","))
    except ValueError:
        sys.exit("--bbox needs four numbers: west,south,east,north")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        sys.exit("--bbox out of range: need -180<=west<east<=180 and -90<=south<north<=90")
    return west, south, east, north


def cells_in_box(bbox: tuple[float, float, float, float]) -> int:
    west, south, east, north = bbox
    nlon = round((east - west) / LON_STEP) + 1
    nlat = round((north - south) / LAT_STEP) + 1
    return nlon * nlat


def collection_variables(collections: dict[str, frozenset[str]]) -> dict[str, list[str]]:
    """Variables Harmony must keep, per collection: the union over the selected groups."""
    return {
        coll: sorted({v for g in groups for v in GROUPS[g]["variables"]})
        for coll, groups in collections.items()
    }


def est_mb_per_file(n_variables: int, bbox: tuple[float, float, float, float]) -> float:
    return n_variables * cells_in_box(bbox) * BYTES_PER_VALUE / 1e6


def resolve(args: argparse.Namespace) -> tuple[dict[str, frozenset[str]], date, date, tuple]:
    """Which collections the chosen groups need, the date window and the box."""
    collections: dict[str, set[str]] = {}
    for group in args.only:
        collections.setdefault(GROUPS[group]["collection"], set()).add(group)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if start < FIRST_DATE or start > end:
        sys.exit(f"Bad window: need {FIRST_DATE} <= --start <= --end (got {start} to {end}).")
    bbox = parse_bbox(args.bbox) if args.bbox else DEFAULT_BBOX
    return {c: frozenset(g) for c, g in collections.items()}, start, end, bbox


def print_summary(granules: list[Granule], groups: list[str], bbox: tuple) -> None:
    """One row per requested group with the estimated subset size, then the total."""
    collections = {g: GROUPS[g]["collection"] for g in groups}
    per_coll = {
        c: frozenset(g for g in groups if GROUPS[g]["collection"] == c)
        for c in set(collections.values())
    }
    variables = collection_variables(per_coll)
    print(f"Box (west,south,east,north): {','.join(str(x) for x in bbox)}")
    print(f"{'GROUP':<18} {'COLLECTION':<11} {'FILES':>6} {'EST_GB':>8}  DATES")
    for group in groups:
        coll = collections[group]
        mine = [g for g in granules if g.collection == coll]
        if not mine:
            print(f"{group:<18} {coll:<11} {0:>6} {0:>8.3f}  none found")
            continue
        est_gb = len(mine) * est_mb_per_file(len(variables[coll]), bbox) / 1000
        first, last = min(g.time_start for g in mine)[:7], max(g.time_start for g in mine)[:7]
        print(f"{group:<18} {coll:<11} {len(mine):>6} {est_gb:>8.3f}  {first} to {last}")
    total_gb = (
        sum(
            sum(1 for g in granules if g.collection == c) * est_mb_per_file(len(variables[c]), bbox)
            for c in variables
        )
        / 1000
    )
    print(f"\nUnique subset files: {len(granules)}   estimated total: {total_gb:.2f} GB")
    print(
        "Estimate = variables x grid cells in the box x 4 bytes. Files shared by groups count once."
    )


def write_plan(
    path: Path, granules: list[Granule], bbox: tuple, variables: dict[str, list[str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["collection", "name", "time_start", "est_mb", "variables", "groups"])
        for g in granules:
            est = est_mb_per_file(len(variables[g.collection]), bbox)
            writer.writerow(
                [
                    g.collection,
                    g.name,
                    g.time_start,
                    round(est, 3),
                    ";".join(variables[g.collection]),
                    ";".join(sorted(g.groups)),
                ]
            )


def is_hdf5(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(8) == HDF5_MAGIC


def make_client(env: dict[str, str], validate: bool) -> Client:
    user, password = env.get("EARTHDATA_USERNAME"), env.get("EARTHDATA_PASSWORD")
    if not user or not password:
        sys.exit("Missing EARTHDATA_USERNAME / EARTHDATA_PASSWORD in .env (needed for Harmony).")
    return Client(auth=(user, password), should_validate_auth=validate)


def wait_and_resume(client: Client, job_id: str) -> str:
    """Poll a Harmony job to the end. If Harmony pauses it, resume it. Returns the final state."""
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while True:
        state = client.status(job_id).get("status", "")
        if state in DONE_STATES:
            return state
        if state == "paused":
            client.resume(job_id)
        if time.monotonic() > deadline:
            raise TimeoutError(f"Harmony job {job_id} still '{state}' after 6 hours")
        time.sleep(POLL_SECONDS)


def overlapping(spans: list[tuple[date, date]], lo: date, hi: date) -> int:
    """How many granules overlap lo..hi. CMR uses the same rule, so this is the expected count."""
    return sum(1 for first, last in spans if first <= hi and last >= lo)


def chunks_for(
    collection: str, year: int, start: date, end: date, spans: list[tuple[date, date]]
) -> list[tuple[int | None, date, date, int]]:
    """(month or None, first day, last day, expected files) for one collection and year."""
    if collection in DAILY_COLLECTIONS:
        out = []
        for month in range(1, 13):
            first = date(year, month, 1)
            last = date(year, month, calendar.monthrange(year, month)[1])
            lo, hi = max(start, first), min(end, last)
            expected = overlapping(spans, lo, hi)
            if expected and lo <= hi:
                out.append((month, lo, hi, expected))
        return out
    lo, hi = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
    expected = overlapping(spans, lo, hi)
    return [(None, lo, hi, expected)] if expected and lo <= hi else []


def run_job(
    env: dict[str, str],
    concept: str,
    collection: str,
    year: int,
    month: int | None,
    lo: date,
    hi: date,
    variables: list[str],
    bbox: tuple,
    expected: int,
    out_root: Path,
) -> dict:
    """One Harmony job for one collection and one chunk. Never raises: errors go in the row."""
    outdir = out_root / collection / str(year)
    marker = outdir / (".done.json" if month is None else f".done-{month:02d}.json")
    label = f"{year}" if month is None else f"{year}-{month:02d}"
    row = {"collection": collection, "chunk": label, "expected": expected, "job_id": "", "files": 0}
    if marker.exists():
        return {**row, "status": "skipped"}
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        client = make_client(env, validate=False)
        west, south, east, north = bbox
        request = Request(
            collection=Collection(id=concept),
            spatial=BBox(west, south, east, north),
            temporal={
                "start": datetime(lo.year, lo.month, lo.day),
                "stop": datetime(hi.year, hi.month, hi.day, 23, 59, 59),
            },
            variables=variables,
            format="application/x-netcdf4",
        )
        job_id = client.submit(request)
        row["job_id"] = job_id
        state = wait_and_resume(client, job_id)
        if state == "failed":
            return {**row, "status": "failed: Harmony job failed"}
        paths = [
            Path(str(fut.result())) for fut in client.download_all(job_id, directory=str(outdir))
        ]
        bad = [p.name for p in paths if not is_hdf5(p)]
        row["files"] = len(paths)
        if bad:
            return {**row, "status": f"failed: {len(bad)} output files are not netCDF-4"}
        if len(paths) != expected:
            return {**row, "status": f"failed: got {len(paths)} files, CMR has {expected}"}
        marker.write_text(
            json.dumps({"job_id": job_id, "state": state, "files": len(paths)}, indent=2),
            encoding="utf-8",
        )
        return {**row, "status": "ok"}
    except Exception as err:  # noqa: BLE001 - recorded in the manifest, the other jobs carry on
        return {**row, "status": f"failed: {err}"[:200]}


def cmd_plan(args: argparse.Namespace) -> None:
    collections, start, end, bbox = resolve(args)
    granules = discover(collections, start, end, args.workers)
    print_summary(granules, args.only, bbox)
    plan_path = DATA_DIR / "plan.csv"
    write_plan(plan_path, granules, bbox, collection_variables(collections))
    print(
        f"\nDry run only: no Harmony jobs run. File list written to {plan_path.relative_to(ROOT)}"
    )


def cmd_download(args: argparse.Namespace) -> None:
    if not args.confirm:
        sys.exit(
            "Refusing to download without --confirm. Run `plan`, review the summary, then re-run."
        )
    collections, start, end, bbox = resolve(args)
    env = load_env()
    make_client(env, validate=True)  # fail early on bad Earthdata credentials
    granules = discover(collections, start, end, args.workers)
    spans: dict[str, list[tuple[date, date]]] = {c: [] for c in collections}
    for g in granules:
        first = date.fromisoformat(g.time_start[:10])
        last = first
        if g.collection not in DAILY_COLLECTIONS:  # monthly files cover their whole month
            last = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
        spans[g.collection].append((first, last))
    variables = collection_variables(collections)
    concepts = {c: concept_id(c) for c in collections}
    out_root = DATA_DIR / "subset"
    jobs = []
    for coll in sorted(collections):
        for year in range(start.year, end.year + 1):
            for month, lo, hi, expected in chunks_for(coll, year, start, end, spans[coll]):
                jobs.append((coll, year, month, lo, hi, expected))
    print(f"Submitting {len(jobs)} Harmony jobs (per year, or per month for M2SDNXSLV)")
    print(f"Running {args.workers} at a time")
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(
                run_job,
                env,
                concepts[c],
                c,
                y,
                m,
                lo,
                hi,
                variables[c],
                bbox,
                n,
                out_root,
            )
            for c, y, m, lo, hi, n in jobs
        ]
        for i, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            rows.append(row)
            print(f"[{i}/{len(jobs)}] {row['status'][:60]:<60} {row['collection']} {row['chunk']}")
    failed = sum(r["status"].startswith("failed") for r in rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["status"])
        writer.writeheader()
        writer.writerows(rows)
    provenance = {
        "source": "NASA GES DISC MERRA-2 via Harmony subsetting, CMR for file lists",
        "version": VERSION,
        "groups": args.only,
        "window": f"{start}..{end}",
        "bbox_west_south_east_north": list(bbox),
        "variables": variables,
        "jobs": len(rows),
        "failed": failed,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (DATA_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(f"\nDone: {len(rows) - failed} jobs ok or skipped, {failed} failed.")
    print(f"Manifest: {(DATA_DIR / 'manifest.csv').relative_to(ROOT)}")
    if failed:
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "download"):
        s = sub.add_parser(name)
        s.add_argument(
            "--start", default=FIRST_DATE.isoformat(), help="YYYY-MM-DD (default 1980-01-01)"
        )
        s.add_argument("--end", default=date.today().isoformat(), help="YYYY-MM-DD (default today)")
        s.add_argument("--only", nargs="+", choices=sorted(GROUPS), default=sorted(GROUPS))
        s.add_argument(
            "--bbox", default="", help="west,south,east,north (default Asia-Pacific box)"
        )
        s.add_argument("--workers", type=int, default=2, help="Harmony jobs at once (default 2)")
    sub.choices["download"].add_argument(
        "--confirm", action="store_true", help="required to really run"
    )
    args = p.parse_args(argv)
    (cmd_plan if args.cmd == "plan" else cmd_download)(args)


if __name__ == "__main__":
    main()
