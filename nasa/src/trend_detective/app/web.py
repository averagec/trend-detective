"""Interactive trend app. Pick a question, a region and a year window; the trend is worked out on
each request from the processed monthly data.

Owns: the HTTP routes and the page. Statistics come from core/ through
process/analyse_trends.build(). The browser computes nothing: it draws what the server returns.

Run (from the project root):
    python src/trend_detective/app/web.py
    python src/trend_detective/app/web.py --input some/monthly_regional.csv --port 5000
Then open http://127.0.0.1:5000

The website (web/, built with `npm run build` into web/dist) is served at / when that folder
exists, next to the JSON API; the plain internal page stays at /classic. Pass --web-dir to serve
another build, or --web-dir "" to serve only the plain page.

Needs data/processed/merra2/monthly_regional.csv (from process/merra2_clean.py).
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.catalog.regions import REGIONS  # noqa: E402
from trend_detective.catalog.variables import VARIABLES  # noqa: E402
from trend_detective.process.analyse_trends import build, build_custom, load, scan  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "processed" / "merra2" / "monthly_regional.csv"
DEFAULT_IMAGES = ROOT / "data" / "demo" / "images"  # made by scripts/render_demo_images.py
DEFAULT_WEB = ROOT / "web" / "dist"  # the built website (npm run build in web/)
OCEAN_IMAGES = ("ocean_ssh_mean.png", "sar_browse_scenes.png")

# Limits for POST /api/analyse (documented in docs/api.md)
MAX_BODY_BYTES = 128 * 1024  # 2000 numbers of 25 characters is about 50 KiB
MIN_VALUES, MAX_VALUES = 24, 2000  # 24: two years, the least the statistics accept
MAX_LABEL, MAX_UNIT = 80, 20
MAX_ABS_VALUE = 1e12  # anything physical is far smaller; keeps the sums of squares finite
START_RE = re.compile(r"([0-9]{4})-([0-9]{2})")


def _text_field(body: dict, key: str, longest: int) -> str:
    value = body[key]
    if not isinstance(value, str) or not value.strip() or len(value) > longest:
        abort(400, description=f"{key} must be text of 1 to {longest} characters")
    if not value.isprintable():
        abort(400, description=f"{key} must not contain control characters")
    return value.strip()


def parse_series_body(body: object) -> tuple[str, str, int, int, list[float | None]]:
    """Check the JSON body of POST /api/analyse. Aborts with a 400 and a clear message.

    Returns (label, unit, start_year, start_month, values), values being floats or None.
    """
    if not isinstance(body, dict):
        abort(400, description="body must be a JSON object (send Content-Type: application/json)")
    missing = [k for k in ("label", "unit", "start", "values") if k not in body]
    if missing:
        abort(400, description=f"missing field(s): {', '.join(missing)}")
    label = _text_field(body, "label", MAX_LABEL)
    unit = _text_field(body, "unit", MAX_UNIT)

    start = START_RE.fullmatch(body["start"]) if isinstance(body["start"], str) else None
    if start is None or not 1 <= int(start[2]) <= 12 or int(start[1]) < 1:
        abort(400, description='start must be a month like "1995-03"')
    year, month = int(start[1]), int(start[2])

    raw = body["values"]
    if not isinstance(raw, list) or not MIN_VALUES <= len(raw) <= MAX_VALUES:
        got = f" (got {len(raw)})" if isinstance(raw, list) else ""
        abort(
            400, description=f"values must be a list of {MIN_VALUES} to {MAX_VALUES} entries{got}"
        )
    values: list[float | None] = []
    for i, v in enumerate(raw):
        if v is None:
            values.append(None)
            continue
        # bool is a kind of int in Python, and "true" is not a measurement
        ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        try:
            x = float(v) if ok else math.nan  # a huge integer raises OverflowError
        except OverflowError:
            x = math.nan
        if not math.isfinite(x) or abs(x) > MAX_ABS_VALUE:
            abort(
                400,
                description=f"values[{i}] must be a number (finite, at most {MAX_ABS_VALUE:g} "
                "in size) or null",
            )
        values.append(x)
    n_numbers = sum(v is not None for v in values)
    if n_numbers < MIN_VALUES:
        abort(400, description=f"values needs at least {MIN_VALUES} numbers, got {n_numbers}")
    if year + (month - 1 + len(values) - 1) // 12 > 9999:
        abort(400, description="the series would run past the year 9999")
    return label, unit, year, month, values


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


def create_app(
    input_csv: Path = DEFAULT_INPUT,
    images_dir: Path = DEFAULT_IMAGES,
    web_dir: Path | None = None,
) -> Flask:
    """`web_dir`: a built website to serve at / (needs an index.html). None: the plain page."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES  # a larger body is refused with a 413
    store = Store(Path(input_csv))
    images_dir = Path(images_dir)
    site = Path(web_dir) if web_dir else None
    if site is not None and not (site / "index.html").is_file():
        site = None  # not built: fall back to the plain page

    def json_error(message: str, status: int):
        """Every /api/* error has this shape, so the page can always call response.json()."""
        response = jsonify({"error": message, "status": status})
        response.status_code = status
        return response

    @app.errorhandler(FileNotFoundError)
    def missing_data(err):
        return json_error(str(err), 503)

    @app.errorhandler(HTTPException)
    def http_error(err):
        if not request.path.startswith("/api/"):
            return err  # pages keep Flask's normal HTML error
        response = json_error(err.description or err.name, err.code or 500)
        allow = err.get_response().headers.get("Allow")  # a 405 must still say what is allowed
        if allow:
            response.headers["Allow"] = allow
        return response

    @app.errorhandler(Exception)
    def unexpected_error(err):
        if not request.path.startswith("/api/"):
            raise err
        app.logger.exception("unexpected error in %s", request.path)
        return json_error("internal error", 500)  # no details: they may name files or code

    @app.get("/")
    def index():
        if site is not None:
            return send_from_directory(site, "index.html")
        return render_template("index.html")

    @app.get("/classic")
    def classic():
        return render_template("index.html")

    if site is not None:

        @app.get("/<path:name>")
        def site_file(name: str):
            """The website's own files (assets, data, images). Never an /api path."""
            if name.startswith("api/"):
                abort(404)
            return send_from_directory(site, name)  # refuses paths that leave the folder

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

    def year_window() -> tuple[int, int]:
        """The `from` and `to` query parameters (default: the whole record), validated."""
        try:
            first = int(request.args.get("from", store.years()[0]))
            last = int(request.args.get("to", store.years()[1]))
        except ValueError:
            abort(400, description="from and to must be years")
        if not (1 <= first <= 9999 and 1 <= last <= 9999):
            abort(400, description="from and to must be years between 1 and 9999")
        if first > last:
            abort(400, description="from must be on or before to")
        return first, last

    @app.get("/api/trend")
    def trend():
        variable = request.args.get("variable", "")
        region = request.args.get("region", "")
        first, last = year_window()
        series = store.series()
        entry = series.get((region, variable))
        if entry is None:
            abort(404, description=f"no data for {variable} in {region}")
        try:
            result = build(region, variable, entry, first, last)
        except ValueError as err:
            abort(400, description=str(err))
        return jsonify(result)

    @app.get("/api/scan")
    def scan_all():
        """Every region x variable in the data, with the multiple-testing correction."""
        first, last = year_window()
        try:
            result = scan(store.series(), first, last)
        except ValueError as err:
            abort(400, description=str(err))
        return jsonify(result)

    @app.post("/api/analyse")
    def analyse():
        """Analyse a monthly series the user sends. Nothing is stored or written."""
        try:
            body = request.get_json(silent=True)
        except RecursionError:  # absurdly nested JSON; json.loads raises this, not ValueError
            body = None
        label, unit, year, month, values = parse_series_body(body)
        return jsonify(build_custom(label, unit, year, month, values))

    return app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--web-dir", type=Path, default=DEFAULT_WEB, help="built website to serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args(argv)
    web_dir = args.web_dir if str(args.web_dir) else None
    if web_dir is not None and not (web_dir / "index.html").is_file():
        print(f"No website build in {web_dir}: serving the plain page. "
              "Build it with: cd web && npm ci && npm run build")  # fmt: skip
    create_app(args.input, web_dir=web_dir).run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
