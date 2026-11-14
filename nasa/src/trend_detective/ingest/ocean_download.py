"""Download NASA ocean granules for a region and date range from NASA Earthdata.

Owns: CMR discovery, Earthdata-authenticated downloads, manifests. No analysis here.
Standard library only, so it runs on any laptop with Python 3.10+.

Examples (Asia-Pacific box, 1992-2022):
    # 1. See which collections exist and how many granules fall in the window (no download)
    python src/trend_detective/ingest/ocean_download.py search --keyword "sea surface height"
    # 2. Download every collection that matches (skips any over --max-granules)
    python src/trend_detective/ingest/ocean_download.py download --keyword "sea surface height"
    # 3. Or download specific collections by concept ID, copied from the search output
    python src/trend_detective/ingest/ocean_download.py download --concept-id C1234567-PODAAC

Credentials: EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env, never in code.
The CMR search needs no login. Downloads do.
Writes data/raw/ocean/<short_name>/ (git-ignored): granule files, manifest.csv, provenance.json.
Downloads are resumable: files already on disk are kept and skipped.
"""

from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CMR = "https://cmr.earthdata.nasa.gov/search"
ASIA_PACIFIC = "60,-50,180,60"  # west,south,east,north (same box as sar.py)
DATA_DIR = ROOT / "data" / "raw" / "ocean"
UA = {"User-Agent": "trend-detective-ocean/0.1"}
MANIFEST_COLS = ["name", "time_start", "url", "bytes", "status", "local"]


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    """Parse KEY=VALUE lines from .env. Lines without '=' (such as bare tokens) are ignored."""
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip("'\"")
    return env


def window(start: int, end: int) -> str:
    return f"{start}-01-01T00:00:00Z,{end}-12-31T23:59:59Z"


def common_params(start: int, end: int, bbox: str) -> list[tuple[str, str]]:
    return [("temporal", window(start, end)), ("bounding_box", bbox)]


def cmr_get(endpoint: str, params: list[tuple[str, str]]) -> tuple[dict, dict[str, str]]:
    """Call the public CMR search API. Returns (json body, lower-cased response headers)."""
    url = f"{CMR}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        headers = {k.lower(): v for k, v in r.headers.items()}
        return json.load(r), headers


def find_collections(keyword: str, start: int, end: int, bbox: str, limit: int) -> list[dict]:
    params = [("keyword", keyword), ("page_size", str(limit)), *common_params(start, end, bbox)]
    body, _ = cmr_get("collections.json", params)
    return body["feed"]["entry"]


def get_collections(concept_ids: list[str]) -> list[dict]:
    params = [("concept_id", c) for c in concept_ids] + [("page_size", str(len(concept_ids)))]
    body, _ = cmr_get("collections.json", params)
    return body["feed"]["entry"]


def granule_count(concept_id: str, start: int, end: int, bbox: str) -> int:
    params = [("concept_id", concept_id), ("page_size", "0"), *common_params(start, end, bbox)]
    _, headers = cmr_get("granules.json", params)
    return int(headers.get("cmr-hits", "0"))


def data_url(entry: dict) -> str | None:
    """The downloadable file link of a granule (skips metadata, thumbnails and checksums)."""
    for link in entry.get("links", []):
        href = link.get("href", "")
        if link.get("rel", "").endswith("/data#") and not href.endswith(
            (".xml", ".html", ".md5", ".jpg", ".png")
        ):
            return href
    return None


def list_granules(concept_id: str, start: int, end: int, bbox: str, want: int) -> list[dict]:
    """Page through CMR until `want` granules with download links are collected."""
    found: list[dict] = []
    page = 1
    while len(found) < want:
        params = [
            ("concept_id", concept_id),
            ("page_size", str(min(2000, want))),
            ("page_num", str(page)),
            *common_params(start, end, bbox),
        ]
        body, _ = cmr_get("granules.json", params)
        entries = body["feed"]["entry"]
        if not entries:
            break
        for entry in entries:
            url = data_url(entry)
            if url:
                found.append(
                    {
                        "name": Path(urllib.parse.urlparse(url).path).name,
                        "time_start": entry.get("time_start", ""),
                        "url": url,
                    }
                )
        page += 1
    return found[:want]


def authed_opener(env: dict[str, str]) -> urllib.request.OpenerDirector:
    """Opener that answers the Earthdata Login challenge and keeps its session cookie."""
    user = env.get("EARTHDATA_USERNAME")
    password = env.get("EARTHDATA_PASSWORD")
    if not user or not password:
        sys.exit("Missing EARTHDATA_USERNAME / EARTHDATA_PASSWORD in .env (needed to download).")
    mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, "https://urs.earthdata.nasa.gov", user, password)
    return urllib.request.build_opener(
        urllib.request.HTTPBasicAuthHandler(mgr),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )


def fetch(opener: urllib.request.OpenerDirector, url: str, dest: Path) -> int:
    """Stream one file to a .part file, then rename it, so a failed run never leaves a half file."""
    tmp = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers=UA)
    with opener.open(request, timeout=900) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)
    return dest.stat().st_size


def concept_id_of(c: dict) -> str:
    """CMR JSON carries the concept ID in "id"; fall back to "concept_id" if present."""
    return c.get("id") or c.get("concept_id") or ""


def describe(c: dict, n: int) -> str:
    end = c.get("time_end") or "present"
    return (
        f"{c.get('short_name', '?'):<26} v{c.get('version_id', '?'):<5} "
        f"{c.get('time_start', '')[:10]} to {end[:10]:<10}  granules {n:>6}  {concept_id_of(c)}"
    )


def resolve(args: argparse.Namespace) -> list[dict]:
    if args.concept_id:
        return get_collections(args.concept_id)
    seen: dict[str, dict] = {}
    for keyword in args.keyword:
        for c in find_collections(keyword, args.start, args.end, args.bbox, args.limit):
            seen.setdefault(concept_id_of(c), c)
    return list(seen.values())


def cmd_search(args: argparse.Namespace) -> None:
    for c in resolve(args):
        n = granule_count(concept_id_of(c), args.start, args.end, args.bbox)
        print(describe(c, n))


def cmd_download(args: argparse.Namespace, out_root: Path = DATA_DIR) -> None:
    env = load_env()
    opener = None
    for c in resolve(args):
        short = c.get("short_name", "unknown")
        n = granule_count(concept_id_of(c), args.start, args.end, args.bbox)
        print(describe(c, n))
        if n == 0:
            continue
        if n > args.max_granules and not args.include_large:
            print(f"  skipped: {n} granules > --max-granules {args.max_granules}")
            continue
        if args.dry_run:
            continue
        if opener is None:
            opener = authed_opener(env)
        out_dir = out_root / short
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for g in list_granules(concept_id_of(c), args.start, args.end, args.bbox, n):
            dest = out_dir / g["name"]
            row = {**g, "local": str(dest.relative_to(ROOT)), "bytes": "", "status": "ok"}
            try:
                if dest.exists():
                    row["bytes"] = dest.stat().st_size
                else:
                    row["bytes"] = fetch(opener, g["url"], dest)
            except (urllib.error.URLError, OSError) as err:
                row["status"] = f"failed: {err}"
            print(f"  {row['status'][:4]}  {g['name']}")
            rows.append(row)
        with open(out_dir / "manifest.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_COLS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        provenance = {
            "short_name": short,
            "concept_id": concept_id_of(c),
            "version_id": c.get("version_id"),
            "title": c.get("title"),
            "window": f"{args.start}-{args.end}",
            "bbox_west_south_east_north": args.bbox,
            "granules_requested": n,
            "granules_ok": sum(r["status"] == "ok" for r in rows),
            "source": "NASA CMR search, NASA Earthdata download",
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("search", "download"):
        s = sub.add_parser(name)
        s.add_argument("--keyword", action="append", default=[], help="repeatable")
        s.add_argument("--concept-id", action="append", default=[], help="repeatable")
        s.add_argument("--start", type=int, default=1992)
        s.add_argument("--end", type=int, default=2022)
        s.add_argument("--bbox", default=ASIA_PACIFIC, help="west,south,east,north")
        s.add_argument("--limit", type=int, default=20, help="max collections per keyword")
        if name == "download":
            s.add_argument("--max-granules", type=int, default=400)
            s.add_argument("--include-large", action="store_true")
            s.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if not args.keyword and not args.concept_id:
        p.error("give at least one --keyword or --concept-id")
    (cmd_search if args.cmd == "search" else cmd_download)(args)


if __name__ == "__main__":
    main()
