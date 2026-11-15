"""Build Indonesia's province outlines and city list for the map, from Natural Earth.

Inputs (download once, any folder):
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson

Outputs:
    web/public/data/indonesia_provinces.json  one SVG path per province (sea_map.json projection)
    data/processed/indonesia/cities.csv         name, province, lat, lon, population, capital,
                                                coast_km
Natural Earth is public domain.

A city's province comes from point-in-polygon on the province outlines, not from the places file's
own adm1name (that field is wrong for some cities, e.g. Bekasi). coast_km is the distance to the
nearest Indonesian coastline (country outline in sea_map.json).

Examples:
    python scripts/build_indonesia_geo.py --ne-dir /path/to/natural-earth
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PROV = ROOT / "web" / "public" / "data" / "indonesia_provinces.json"
OUT_CITY = ROOT / "data" / "processed" / "indonesia" / "cities.csv"
SEA_MAP = ROOT / "web" / "public" / "data" / "sea_map.json"

PROVINCE_NAMES = {
    "Jakarta Raya": "DKI Jakarta",
    "Yogyakarta": "DI Yogyakarta",
    "Bangka-Belitung": "Bangka Belitung",
}
CITY_NAMES = {"Bandjarmasin": "Banjarmasin", "Pakalongan": "Pekalongan"}
# Cities on a province border where the 1:10m outlines put them on the wrong side.
PROVINCE_FIX = {"Bekasi": "Jawa Barat"}
MIN_RING_AREA = 0.002  # square degrees; drops islets too small to see on the map


def rings(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return polys


def ring_area(r):
    return abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2)


def to_path(geom):
    out = []
    for poly in rings(geom):
        for r in poly:
            if ring_area(r) < MIN_RING_AREA:
                continue
            pts, last = [], None
            for lon, lat in r:
                p = f"{lon + 180:.2f} {90 - lat:.2f}"
                if p != last:
                    pts.append(p)
                    last = p
            if len(pts) > 3:
                out.append("M" + "L".join(pts) + "Z")
    return "".join(out)


def inside(geom, lon, lat):
    for poly in rings(geom):
        r, c = poly[0], False
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i], r[i - 1]
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                c = not c
        if c:
            return True
    return False


def coast_segments():
    d = json.loads(SEA_MAP.read_text())["sea"]["Indonesia"]
    segs = []
    for ring in re.findall(r"M([^Z]+)Z", d):
        pts = [tuple(float(v) for v in p.split()) for p in ring.split("L")]
        pts = [(x - 180, 90 - y) for x, y in pts]
        segs += list(zip(pts, pts[1:] + pts[:1], strict=True))
    return segs


def coast_km(lon, lat, segs):
    k = math.cos(math.radians(lat))
    best = float("inf")
    for (x1, y1), (x2, y2) in segs:
        ax, ay, bx, by = (x1 - lon) * k, y1 - lat, (x2 - lon) * k, y2 - lat
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best * 111.32


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ne-dir", type=Path, required=True)
    a = ap.parse_args()
    prov = json.loads((a.ne_dir / "ne_10m_admin_1_states_provinces.geojson").read_text())
    places = json.loads((a.ne_dir / "ne_10m_populated_places_simple.geojson").read_text())

    provinces = {}
    for f in prov["features"]:
        if f["properties"].get("adm0_a3") != "IDN":
            continue
        name = PROVINCE_NAMES.get(f["properties"]["name"], f["properties"]["name"])
        provinces[name] = f["geometry"]
    OUT_PROV.write_text(
        json.dumps(
            {
                "source": "Natural Earth 1:10m admin-1 (public domain)",
                "provinces": {n: to_path(g) for n, g in sorted(provinces.items())},
            },
            separators=(",", ":"),
        )
    )

    segs = coast_segments()
    cities = {}
    for f in places["features"]:
        p = f["properties"]
        if p.get("adm0_a3") != "IDN":
            continue
        lon, lat = float(p["longitude"]), float(p["latitude"])
        name = CITY_NAMES.get(p["name"], p["name"])
        province = next((n for n, g in provinces.items() if inside(g, lon, lat)), None)
        province = PROVINCE_FIX.get(name, province)
        if province is None:
            province = PROVINCE_NAMES.get(p["adm1name"], p["adm1name"])
        row = {
            "name": name,
            "province": province,
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "population": int(p["pop_max"]),
            "capital": p["featurecla"] in ("Admin-0 capital", "Admin-1 capital"),
            "coast_km": round(coast_km(lon, lat, segs), 1),
        }
        if name not in cities or row["population"] > cities[name]["population"]:
            cities[name] = row

    OUT_CITY.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CITY.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(next(iter(cities.values()))), lineterminator="\n")
        w.writeheader()
        for row in sorted(cities.values(), key=lambda r: -r["population"]):
            w.writerow(row)
    print(f"{len(provinces)} provinces -> {OUT_PROV.relative_to(ROOT)}")
    print(f"{len(cities)} cities -> {OUT_CITY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
