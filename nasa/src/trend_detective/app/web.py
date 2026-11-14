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
import sys
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.catalog.regions import REGIONS  # noqa: E402
from trend_detective.catalog.variables import VARIABLES  # noqa: E402
from trend_detective.process.analyse_trends import build, load  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "processed" / "merra2" / "monthly_regional.csv"
DEFAULT_IMAGES = ROOT / "data" / "demo" / "images"  # made by scripts/render_demo_images.py
OCEAN_IMAGES = ("ocean_ssh_mean.png", "sar_browse_scenes.png")


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


def create_app(input_csv: Path = DEFAULT_INPUT, images_dir: Path = DEFAULT_IMAGES) -> Flask:
    app = Flask(__name__)
    store = Store(Path(input_csv))
    images_dir = Path(images_dir)

    @app.errorhandler(FileNotFoundError)
    def missing_data(err):
        return jsonify({"error": str(err)}), 503

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
