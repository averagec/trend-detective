"""Environment smoke test: python src/trend_detective/ingest/smoke_test.py

Checks .env keys, the NASA api.nasa.gov key, Earthdata reachability, and fetches the
Singapore tide-gauge records from PSMSL. Never prints secret values.
"""
import io
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

NAMES = ("SINGAPORE", "TANJONG", "SEMBAWANG", "KEPPEL")
ROOT = Path(__file__).resolve().parents[3]


def load_env() -> None:
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": "trend-detective-smoke/0.1"})
    return urllib.request.urlopen(req, timeout=timeout)


def step(name: str, fn) -> bool:
    try:
        print(f"[ OK ] {name}: {fn()}")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        body = body.replace(os.environ.get("NASA_API_KEY") or "\0", "<key>")
        print(f"[FAIL] {name}: HTTP {e.code}: {body}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        return False


def nasa_key():
    key = os.environ.get("NASA_API_KEY")
    if not key:
        raise RuntimeError("NASA_API_KEY not set (.env missing or empty)")
    bad = any(c in key for c in " '\"")
    print(f"        key length={len(key)} (NASA keys are 40 chars), has_space_or_quote={bad}")
    r = get(f"https://api.nasa.gov/EPIC/api/natural?api_key={key}")
    left = r.headers.get("X-RateLimit-Remaining")
    return f"HTTP {r.status}, rate-limit remaining={left}"


def cmr():
    r = get("https://cmr.earthdata.nasa.gov/search/collections.json?page_size=1")
    return f"HTTP {r.status}"


def singapore():
    url = "https://psmsl.org/data/obtaining/rlr.monthly.data/rlr_monthly.zip"
    z = zipfile.ZipFile(io.BytesIO(get(url, 120).read()))
    lst = next(n for n in z.namelist() if n.endswith("filelist.txt"))
    hits = []
    for row in z.read(lst).decode("latin-1").splitlines():
        p = [x.strip() for x in row.split(";")]
        if len(p) >= 4 and any(w in p[3].upper() for w in NAMES):
            hits.append(p)
    if not hits:
        raise RuntimeError("no Singapore stations in PSMSL RLR list")
    for sid, lat, lon, name, *_ in hits:
        f = next(n for n in z.namelist() if n.endswith(f"/{sid}.rlrdata"))
        rows = [r for r in z.read(f).decode().splitlines() if r.strip()]
        yrs = [float(r.split(";")[0]) for r in rows]
        print(f"        station {sid} {name} ({lat},{lon}): {len(rows)} records,"
              f" {min(yrs):.1f}-{max(yrs):.1f}")
        print(f"        first: {rows[0]}\n        last : {rows[-1]}")
    return f"{len(hits)} station(s)"


if __name__ == "__main__":
    load_env()
    for k in ("NASA_API_KEY", "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD"):
        print(f"[env ] {k}: {'set' if os.environ.get(k) else 'MISSING'}")
    ok = [step("api.nasa.gov key (EPIC)", nasa_key), step("Earthdata CMR reachable", cmr),
          step("Singapore tide gauge (PSMSL)", singapore)]
    sys.exit(0 if all(ok) else 1)
