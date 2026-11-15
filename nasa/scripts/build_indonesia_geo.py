"""Build Indonesia's province outlines and city list for the map, from Natural Earth.

Inputs (download once, any folder):
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_1_states_provinces.geojson
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson
    https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson

Outputs:
    web/public/data/indonesia_provinces.json  one SVG path per province (sea_map.json projection)
    data/processed/indonesia/cities.csv         name, region, province, lat, lon, population,
                                                capital, coast_km
Natural Earth is public domain.

Only the team's 31 study cities (CITIES below) are kept. Two of them are not in Natural Earth's
places file, so their position and 2020 census population come from EXTRA (Wikipedia infoboxes,
which cite Statistics Indonesia).

A city's province comes from point-in-polygon on the province outlines, not from the places file's
own adm1name (that field is wrong for some cities, e.g. Bekasi). coast_km is the distance to the
nearest coastline in Natural Earth's 1:10m coastline file, which includes small islands such as
Ternate (the coarse map outline does not).

Examples:
    python scripts/build_indonesia_geo.py --ne-dir /path/to/natural-earth
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PROV = ROOT / "web" / "public" / "data" / "indonesia_provinces.json"
OUT_CITY = ROOT / "data" / "processed" / "indonesia" / "cities.csv"

# The study cities, grouped by the regions the team uses in the app.
CITIES = {
    "Sumatra": [
        "Banda Aceh", "Medan", "Padangsidimpuan", "Padang", "Pekanbaru",
        "Jambi", "Bengkulu", "Prabumulih", "Bandar Lampung",
    ],
    "Riau Islands and Bangka Belitung": ["Batam", "Pangkal Pinang"],
    "Java": ["Jakarta", "Tasikmalaya", "Semarang", "Surabaya"],
    "Bali and Nusa Tenggara": ["Denpasar", "Kupang"],
    "Kalimantan": ["Pontianak", "Palangka Raya", "Banjarmasin", "Samarinda", "Tarakan"],
    "Sulawesi": ["Manado", "Gorontalo", "Palu", "Makassar", "Kendari"],
    "Maluku and Papua": ["Ambon", "Ternate", "Sorong", "Jayapura"],
}  # fmt: skip
# Natural Earth spelling -> the spelling used in the app.
CITY_NAMES = {
    "Bandjarmasin": "Banjarmasin",
    "Padangsidempuan": "Padangsidimpuan",
    "Pangkalpinang": "Pangkal Pinang",
    "Palangkaraya": "Palangka Raya",
}
# Not in Natural Earth's places file: (lat, lon, population at the 2020 census).
EXTRA = {
    "Batam": (1.13000, 104.05306, 1196396),  # en.wikipedia.org/wiki/Batam
    "Prabumulih": (-3.43278, 104.23556, 193196),  # en.wikipedia.org/wiki/Prabumulih
}
CAPITALS = {
    "Banda Aceh", "Medan", "Padang", "Pekanbaru", "Jambi", "Bengkulu", "Bandar Lampung",
    "Pangkal Pinang", "Jakarta", "Semarang", "Surabaya", "Denpasar", "Kupang", "Pontianak",
    "Palangka Raya", "Banjarmasin", "Samarinda", "Manado", "Gorontalo", "Palu", "Makassar",
    "Kendari", "Ambon", "Jayapura",
}  # fmt: skip

PROVINCE_NAMES = {
    "Jakarta Raya": "DKI Jakarta",
    "Yogyakarta": "DI Yogyakarta",
    "Bangka-Belitung": "Bangka Belitung",
}
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


def coast_segments(path: Path):
    """Coastline segments (lon, lat pairs) around Indonesia from the 1:10m coastline file."""
    segs = []
    for f in json.loads(path.read_text())["features"]:
        g = f["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for ln in lines:
            for p, q in zip(ln, ln[1:], strict=False):
                if 90 <= p[0] <= 145 and -14 <= p[1] <= 10:
                    segs.append((tuple(p), tuple(q)))
    return segs


def coast_km(lon, lat, segs):
    k = math.cos(math.radians(lat))
    best = float("inf")
    for (x1, y1), (x2, y2) in segs:
        if abs(x1 - lon) > 3 or abs(y1 - lat) > 3:
            continue
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

    segs = coast_segments(a.ne_dir / "ne_10m_coastline.geojson")
    found = {}
    for f in places["features"]:
        p = f["properties"]
        if p.get("adm0_a3") != "IDN":
            continue
        name = CITY_NAMES.get(p["name"], p["name"])
        pos = (float(p["latitude"]), float(p["longitude"]), int(p["pop_max"]))
        if name not in found or pos[2] > found[name][2]:
            found[name] = pos
    found.update(EXTRA)

    cities = {}
    for region, names in CITIES.items():
        for name in names:
            if name not in found:
                raise SystemExit(f"no position for {name}")
            lat, lon, pop = found[name]
            province = next((n for n, g in provinces.items() if inside(g, lon, lat)), None)
            province = PROVINCE_FIX.get(name, province)
            if province is None:
                raise SystemExit(f"{name} is outside every province outline")
            cities[name] = {
                "name": name,
                "region": region,
                "province": province,
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "population": pop,
                "capital": name in CAPITALS,
                "coast_km": round(coast_km(lon, lat, segs), 1),
            }

    OUT_CITY.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CITY.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(next(iter(cities.values()))), lineterminator="\n")
        w.writeheader()
        for row in cities.values():
            w.writerow(row)
    print(f"{len(provinces)} provinces -> {OUT_PROV.relative_to(ROOT)}")
    print(f"{len(cities)} cities -> {OUT_CITY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
