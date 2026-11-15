"""Fetch Sentinel-1 SAR scene lists + browse imagery for coastal-change sites (ASF DAAC).

Coastal change needs ONE consistent view per month: same orbit direction + relative orbit
(path), so geometry doesn't masquerade as shoreline movement. This keeps one scene per month.

Run on a machine that can reach api.daac.asf.alaska.edu, e.g. Singapore east coast:
    python src/trend_detective/ingest/sar.py --bbox 103.95,1.28,104.10,1.40 \
        --start 2015-01-01 --end 2024-12-31 --direction DESCENDING --path 18 --name singapore_east
Omit --path first to see which paths cover the site (printed in the summary), then pin one.
Default bbox is all Asia-Pacific (listing only: too big for a shoreline).

Writes data/raw/sar/<name>/ (git-ignored): scenes.csv, scenes.geojson, browse/*
Only browse quicklooks are downloaded. Full scenes are GBs (needs Earthdata login):
fetch those from the `url` column when we process real backscatter.
"""
import argparse
import csv
import json
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = "https://api.daac.asf.alaska.edu/services/search/param"
ASIA_PACIFIC = "60,-50,180,60"  # west,south,east,north
UA = {"User-Agent": "trend-detective-sar/0.2"}
COLS = ["sceneName", "startTime", "flightDirection", "pathNumber", "polarization", "url", "browse"]


def wkt_box(bbox: str) -> str:
    w, s, e, n = (float(x) for x in bbox.split(","))
    return f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"


def search(a: argparse.Namespace) -> list[dict]:
    q = {
        "platform": "Sentinel-1",
        "processingLevel": "GRD_HD",
        "beamMode": "IW",
        "intersectsWith": wkt_box(a.bbox),
        "start": f"{a.start}T00:00:00Z",
        "end": f"{a.end}T23:59:59Z",
        "maxResults": a.limit,
        "output": "geojson",
    }
    if a.direction:
        q["flightDirection"] = a.direction
    if a.path:
        q["relativeOrbit"] = a.path
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(q)}", headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r).get("features", [])


def one_per_month(features: list[dict]) -> list[dict]:
    """Keep the earliest scene of each calendar month (features are not pre-sorted)."""
    best: dict[str, dict] = {}
    for ft in sorted(features, key=lambda f: f["properties"]["startTime"]):
        best.setdefault(ft["properties"]["startTime"][:7], ft)
    return [best[k] for k in sorted(best)]


def save(features: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    (out / "scenes.geojson").write_text(json.dumps(fc))
    with open(out / "scenes.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for ft in features:
            p = ft["properties"]
            row = {**p, "browse": (p.get("browse") or [""])[0]}
            w.writerow([row.get(c, "") for c in COLS])


def download_browse(features: list[dict], out: Path, n: int) -> int:
    d = out / "browse"
    d.mkdir(exist_ok=True)
    got = 0
    for ft in features[:n]:
        p = ft["properties"]
        links = p.get("browse") or []
        if not links:
            continue
        dest = d / f"{p['sceneName']}{Path(links[0]).suffix or '.png'}"
        try:
            req = urllib.request.Request(links[0], headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                dest.write_bytes(r.read())
            got += 1
        except Exception as e:  # noqa: BLE001
            print(f"  skip {p['sceneName']}: {type(e).__name__}: {e}")
    return got


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--bbox", default=ASIA_PACIFIC, help="west,south,east,north")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default="2024-12-31")
    ap.add_argument("--direction", choices=["ASCENDING", "DESCENDING"], help="orbit direction")
    ap.add_argument("--path", type=int, help="relative orbit (path) to pin")
    ap.add_argument("--name", default="asia_pacific", help="output folder name")
    ap.add_argument("--limit", type=int, default=2000, help="max scenes to request")
    ap.add_argument("--images", type=int, default=6, help="browse images to download")
    a = ap.parse_args()
    feats = search(a)
    paths = Counter(
        (f["properties"]["flightDirection"], f["properties"]["pathNumber"]) for f in feats
    )
    print(f"{len(feats)} scenes for bbox {a.bbox} {a.start}..{a.end}")
    print("most common (direction, path):", paths.most_common(5))
    if a.path or a.direction:
        feats = one_per_month(feats)
        print(f"{len(feats)} months with a scene (one per month kept)")
    if feats:
        out = ROOT / "data" / "raw" / "sar" / a.name
        save(feats, out)
        print(f"{download_browse(feats, out, a.images)} browse images saved; files in {out}")
