"""Interactive trend app. Pick a question, a region and a year window; the trend is worked out on
each request from the processed monthly data.

Owns: the HTTP routes and the page. Statistics come from core/ through
process/analyse_trends.build(). The browser computes nothing: it draws what the server returns.

Run (from the project root):
    python src/trend_detective/app/web.py
    python src/trend_detective/app/web.py --input some/monthly_regional.csv --port 5000
Then open http://127.0.0.1:5000

Needs data/processed/merra2/monthly_regional.csv (from process/merra2_clean.py).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from flask import Flask, abort, jsonify, render_template, request, send_from_directory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.app.event_api import register_event_routes  # noqa: E402
from trend_detective.catalog.regions import REGIONS  # noqa: E402
from trend_detective.catalog.variables import VARIABLES  # noqa: E402
from trend_detective.process.analyse_trends import build, load  # noqa: E402
from trend_detective.process.cell_cube import load as load_cube  # noqa: E402
from trend_detective.process.cities import load_cities  # noqa: E402
from trend_detective.process.regional_map import build_map  # noqa: E402
from trend_detective.process.selection import (  # noqa: E402
    KM_PER_DEG,
    Grid,
    SelectionError,
    analyse_circle,
    analyse_city,
    city_cell,
)

DEFAULT_INPUT = ROOT / "data" / "processed" / "merra2" / "monthly_regional.csv"
DEFAULT_IMAGES = ROOT / "data" / "demo" / "images"  # made by scripts/render_demo_images.py
DEFAULT_CITIES = ROOT / "data" / "catalog" / "cities_idn.csv"  # supplied by the team
DEFAULT_CUBES = ROOT / "data" / "processed" / "cells"  # made by process/cell_cube.py
DEFAULT_PROCESSED = ROOT / "data" / "processed"  # regional CSVs for /api/map
CUBE_FILES = {"merra2": "merra2_idn.npz", "gpcp": "gpcp_idn.npz"}
OCEAN_IMAGES = ("ocean_ssh_mean.png", "sar_browse_scenes.png")
SUMMARY_KEYS = (
    "n_months", "n_years", "ols_per_decade", "ols_ci_per_decade", "ols_p", "ols_significant",
    "sen_per_decade", "mk_p", "mk_significant", "tests_agree", "warnings", "sentence",
)


class Store:
    """Reads the processed CSV once and reloads it when the file changes."""

    def __init__(self, path: Path):
        self.path = path
        self._mtime: float | None = None
        self._series: dict = {}

    def series(self) -> dict:
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} not found. Run process/merra2_clean.py first.")
        mtime = self.path.stat().st_mtime
        if mtime != self._mtime:
            self._series = load(self.path)
            self._mtime = mtime
        return self._series

    def years(self) -> tuple[int, int]:
        periods = [p for entry in self.series().values() for p in entry["values"]]
        return int(min(periods)[:4]), int(max(periods)[:4])


class CubeStore:
    """Loads the per-cell cubes on first use and reloads a cube when its file changes."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._cache: dict[str, tuple[float, object]] = {}

    def get(self, dataset: str):
        path = self.folder / CUBE_FILES[dataset]
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run process/cell_cube.py first.")
        mtime = path.stat().st_mtime
        hit = self._cache.get(dataset)
        if hit is None or hit[0] != mtime:
            hit = (mtime, load_cube(path))
            self._cache[dataset] = hit
        return hit[1]

    def available(self) -> list[str]:
        return [d for d in CUBE_FILES if (self.folder / CUBE_FILES[d]).exists()]


def jsonable(value):
    """Turn numpy values, tuples and NaN into plain JSON (NaN becomes null)."""
    if isinstance(value, np.ndarray):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def iso_periods(periods: list[str]) -> list[str]:
    """YYYYMM (the cube) to YYYY-MM (the API, the same as /api/trend and /api/map)."""
    return [f"{p[:4]}-{p[4:]}" for p in periods]


def land_share_at(cubes: "CubeStore", lat: float, lon: float) -> float | None:
    """Share of months with a MERRA-2 land surface value in the cell that holds (lat, lon)."""
    if not (cubes.folder / CUBE_FILES["merra2"]).exists():
        return None
    cube = cubes.get("merra2")
    if "tsurf" not in cube.values:
        return None
    cell = city_cell(Grid(cube.lat, cube.lon), lat, lon)
    return float(np.isfinite(cube.values["tsurf"][:, cell.i, cell.j]).mean())


def summary_json(s) -> dict:
    return {key: jsonable(getattr(s, key)) for key in SUMMARY_KEYS}


def cell_json(dataset: str, cell) -> dict:
    return {
        "dataset": dataset,
        "lat": cell.lat,
        "lon": cell.lon,
        "width_km": round(cell.width_km, 1),
        "height_km": round(cell.height_km, 1),
    }


def window(cube, variable: str, first: int | None, last: int | None):
    """The months of one variable between two years (inclusive), in order."""
    periods = cube.periods[variable]
    lo = (first or 0) * 100 + 1
    hi = (last or 9999) * 100 + 12
    keep = [k for k, p in enumerate(periods) if lo <= int(p) <= hi]
    if not keep:
        raise ValueError(f"no months for {variable} between {first} and {last}")
    return [periods[k] for k in keep], cube.values[variable][np.array(keep)]


def parse_float(body: dict, key: str) -> float:
    try:
        return float(body[key])
    except (KeyError, TypeError, ValueError):
        abort(400, description=f"{key} must be a number")


def parse_year(body: dict, key: str) -> int | None:
    if body.get(key) in (None, ""):
        return None
    try:
        return int(body[key])
    except (TypeError, ValueError):
        abort(400, description=f"{key} must be a year")


def create_app(
    input_csv: Path = DEFAULT_INPUT,
    images_dir: Path = DEFAULT_IMAGES,
    cities_csv: Path = DEFAULT_CITIES,
    cubes_dir: Path = DEFAULT_CUBES,
    processed_dir: Path = DEFAULT_PROCESSED,
) -> Flask:
    app = Flask(__name__)
    store = Store(Path(input_csv))
    cubes = CubeStore(Path(cubes_dir))
    cities_path = Path(cities_csv)
    images_dir = Path(images_dir)

    @app.errorhandler(FileNotFoundError)
    def missing_data(err):
        return jsonify({"error": str(err)}), 503

    @app.errorhandler(SelectionError)
    def bad_selection(err):
        return jsonify({"error": str(err)}), 400

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/ocean")
    def ocean():
        present = {name: (images_dir / name).exists() for name in OCEAN_IMAGES}
        return render_template("ocean.html", present=present)

    @app.get("/demo/<path:name>")
    def demo_image(name: str):
        return send_from_directory(images_dir, name)

    @app.get("/api/meta")
    def meta():
        series = store.series()
        units = {variable: entry["unit"] for (_, variable), entry in series.items()}
        regions_present = sorted({region for region, _ in series})
        first, last = store.years()
        return jsonify(
            {
                "variables": [
                    {
                        "key": key,
                        "label": VARIABLES[key].label,
                        "question": VARIABLES[key].question,
                        "description": VARIABLES[key].description,
                        "unit": units[key],
                    }
                    for key in sorted(units)
                    if key in VARIABLES
                ],
                "regions": [
                    {"key": r.key, "name": r.name, "why": r.why}
                    for r in REGIONS.values()
                    if r.key in regions_present
                ],
                "years": {"first": first, "last": last},
            }
        )

    @app.get("/api/trend")
    def trend():
        variable = request.args.get("variable", "")
        region = request.args.get("region", "")
        try:
            first = int(request.args.get("from", store.years()[0]))
            last = int(request.args.get("to", store.years()[1]))
        except ValueError:
            abort(400, description="from and to must be years")
        if first > last:
            abort(400, description="from must be on or before to")
        series = store.series()
        entry = series.get((region, variable))
        if entry is None:
            abort(404, description=f"no data for {variable} in {region}")
        try:
            result = build(region, variable, entry, first, last)
        except ValueError as err:
            abort(400, description=str(err))
        return jsonify(result)

    @app.get("/map")
    def map_page():
        return render_template("map.html")

    @app.get("/api/variables")
    def cube_variables():
        out = []
        for dataset in cubes.available():
            cube = cubes.get(dataset)
            for variable in cube.values:
                info = cube.manifest.get("variables", {}).get(variable, {})
                out.append(
                    {
                        "ref": f"{dataset}:{variable}",
                        "dataset": dataset,
                        "label": VARIABLES[variable].label if variable in VARIABLES else variable,
                        "unit": info.get("unit", ""),
                        "first": info.get("first"),
                        "last": info.get("last"),
                    }
                )
        return jsonify({"variables": out})

    @app.get("/api/cities")
    def cities():
        found = load_cities(cities_path)
        return jsonify(
            {
                "cities": [
                    {
                        "id": c.city_id,
                        "name": c.name,
                        "lat": c.lat,
                        "lon": c.lon,
                        "rainfall_source": c.rainfall_source,
                    }
                    for c in found
                ]
            }
        )

    @app.get("/api/cell")
    def cell_for_city():
        city_id = request.args.get("city", "")
        match = [c for c in load_cities(cities_path) if c.city_id == city_id]
        if not match:
            abort(404, description=f"unknown city {city_id!r}")
        city = match[0]
        cells = []
        for dataset in cubes.available():
            cube = cubes.get(dataset)
            grid = Grid(cube.lat, cube.lon)
            cells.append(cell_json(dataset, city_cell(grid, city.lat, city.lon)))
        return jsonify({"city": city.city_id, "cells": cells})

    @app.get("/api/map")
    def regional_map():
        layer = request.args.get("variable", "")
        freq = request.args.get("freq", "monthly")
        first = parse_year(request.args, "from")
        last = parse_year(request.args, "to")
        regions = [r for r in request.args.get("regions", "").split(",") if r] or None
        try:
            return jsonify(build_map(Path(processed_dir), layer, freq, first, last, regions))
        except KeyError:
            abort(404, description=f"unknown variable {layer!r}")
        except ValueError as err:
            abort(400, description=str(err))

    @app.post("/api/analyse")
    def analyse():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="send a JSON object")
        mode = body.get("mode")
        if mode not in ("city", "circle"):
            abort(400, description='mode must be "city" or "circle"')
        refs = body.get("variables")
        if not isinstance(refs, list) or not refs:
            abort(400, description='variables must be a list such as ["merra2:t2m"]')
        first, last = parse_year(body, "from"), parse_year(body, "to")
        if first is not None and last is not None and first > last:
            abort(400, description="from must be on or before to")

        if mode == "city":
            city_id = str(body.get("city_id", ""))
            match = [c for c in load_cities(cities_path) if c.city_id == city_id]
            if not match:
                abort(404, description=f"unknown city {city_id!r}")
            city = match[0]
            lat, lon = city.lat, city.lon
            place = city.name
        else:
            lat, lon = parse_float(body, "lat"), parse_float(body, "lon")
            radius = parse_float(body, "radius_km")
            place = f"the circle of {radius:g} km around {lat:.2f}, {lon:.2f}"

        out = []
        for ref in refs:
            dataset, _, variable = str(ref).partition(":")
            if dataset not in CUBE_FILES:
                abort(400, description=f"unknown dataset {dataset!r}")
            cube = cubes.get(dataset)
            if variable not in cube.values:
                abort(404, description=f"{variable} is not in the {dataset} cube")
            grid = Grid(cube.lat, cube.lon)
            periods, values = window(cube, variable, first, last)
            unit = cube.manifest.get("variables", {}).get(variable, {}).get("unit", "")
            label = VARIABLES[variable].label if variable in VARIABLES else variable
            if mode == "city":
                res = analyse_city(
                    values, periods, grid, lat, lon, unit, f"{label}, {place}", place,
                    land_share=land_share_at(cubes, lat, lon),
                )
                out.append(
                    {
                        "dataset": dataset,
                        "variable": variable,
                        "label": label,
                        "unit": unit,
                        "cell": cell_json(dataset, res.cell),
                        "periods": iso_periods(res.periods),
                        "series": jsonable(res.series),
                        "summary": summary_json(res.summary),
                        "warnings": list(res.warnings),
                    }
                )
            else:
                res = analyse_circle(
                    values, periods, grid, lat, lon, radius, unit, f"{label}, {place}"
                )
                out.append(
                    {
                        "dataset": dataset,
                        "variable": variable,
                        "label": label,
                        "unit": unit,
                        "radius_km": res.radius_km,
                        "cells_in_circle": res.cells_in_circle,
                        "cells_used": res.cells_used,
                        "agreement": {
                            "rising": res.rising,
                            "falling": res.falling,
                            "not_significant": res.not_significant,
                            "expected_per_sign": jsonable(res.expected_per_sign),
                            "slope_min": jsonable(res.slope_min),
                            "slope_max": jsonable(res.slope_max),
                        },
                        "cells": [
                            {
                                "lat": c.lat,
                                "lon": c.lon,
                                "height_km": round(grid.dlat * KM_PER_DEG, 1),
                                "width_km": round(
                                    grid.dlon * KM_PER_DEG * math.cos(math.radians(c.lat)), 1
                                ),
                                "slope_per_decade": jsonable(c.slope),
                                "significant": c.significant,
                                "p_adjusted": jsonable(c.p_adj),
                            }
                            for c in res.cells
                        ],
                        "average": {
                            "periods": iso_periods(res.periods),
                            "series": jsonable(res.average_series),
                            "valid_per_month": jsonable(res.valid_per_month),
                            "summary": summary_json(res.average),
                        },
                        "warnings": list(res.warnings),
                    }
                )
        return jsonify({"mode": mode, "results": out})

    register_event_routes(app, cubes, cities_path)
    return app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args(argv)
    create_app(args.input).run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
