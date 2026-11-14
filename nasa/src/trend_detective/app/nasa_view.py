"""View NASA ocean data: list what the archive holds, summarise what is downloaded, plot a file.

Owns: display only. It computes no trends or p-values. Trend statistics come from
core/trend.py only (AGENTS.md rule 3).

Examples:
    # What the NASA archive holds for the Asia-Pacific box, 1992-2022
    python src/trend_detective/app/nasa_view.py catalog --keyword "sea surface height"
    # What is already downloaded to data/raw/ocean/
    python src/trend_detective/app/nasa_view.py local
    # List the variables in one file, then plot one of them
    python src/trend_detective/app/nasa_view.py plot data/raw/ocean/<short_name>/<file>.nc
    python src/trend_detective/app/nasa_view.py plot <file.nc> --var <name>

Plotting needs: pip install xarray netCDF4 matplotlib numpy
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from trend_detective.ingest.ocean_download import (  # noqa: E402
    ASIA_PACIFIC,
    DATA_DIR,
    concept_id_of,
    describe,
    find_collections,
    granule_count,
)


def cmd_catalog(args: argparse.Namespace) -> None:
    seen: dict[str, dict] = {}
    for keyword in args.keyword:
        for c in find_collections(keyword, args.start, args.end, args.bbox, args.limit):
            seen.setdefault(concept_id_of(c), c)
    if not seen:
        print("No collections matched. Try a broader keyword.")
    for c in seen.values():
        print(describe(c, granule_count(concept_id_of(c), args.start, args.end, args.bbox)))


def cmd_local(_: argparse.Namespace) -> None:
    manifests = sorted(DATA_DIR.glob("*/manifest.csv"))
    if not manifests:
        print(f"Nothing downloaded yet under {DATA_DIR.relative_to(ROOT)}.")
        return
    print(f"{'collection':<26} {'ok':>5} {'failed':>7} {'MB':>9}  {'first':<10} {'last':<10}")
    for path in manifests:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ok = [r for r in rows if r["status"] == "ok"]
        mb = sum(int(r["bytes"] or 0) for r in ok) / 1e6
        times = sorted(r["time_start"][:10] for r in ok if r["time_start"])
        first, last = (times[0], times[-1]) if times else ("-", "-")
        failed = len(rows) - len(ok)
        print(f"{path.parent.name:<26} {len(ok):>5} {failed:>7} {mb:>9.1f}  {first:<10} {last:<10}")


def _coord(ds, options: tuple[str, ...]) -> str:
    return next(n for n in ds.coords if str(n).lower() in options)


def cmd_plot(args: argparse.Namespace) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import xarray as xr
    except ImportError as err:
        sys.exit(f"Missing package: {err.name}. Install: pip install xarray netCDF4 matplotlib")

    path = Path(args.file)
    ds = xr.open_dataset(path)
    if not args.var:
        print(f"Variables in {path.name}:")
        for name, v in ds.data_vars.items():
            print(f"  {name:<28} dims={dict(v.sizes)}  units={v.attrs.get('units', '?')}")
        return

    var = ds[args.var]
    lat = _coord(ds, ("lat", "latitude"))
    lon = _coord(ds, ("lon", "longitude"))
    west, south, east, north = (float(x) for x in args.bbox.split(","))
    region = var.sel({lat: slice(south, north), lon: slice(west, east)})
    has_time = any(d.lower() == "time" for d in region.dims)

    # Area mean weighted by cos(latitude), for display only.
    weights = np.cos(np.deg2rad(region[lat]))
    fig, axes = plt.subplots(2 if has_time else 1, 1, figsize=(9, 8 if has_time else 4.5))
    axes = np.atleast_1d(axes)
    field = region.isel(time=0) if has_time else region
    field.plot(ax=axes[0])
    axes[0].set_title(f"{args.var}: first time step, {args.bbox}")
    if has_time:
        mean = region.weighted(weights).mean(dim=[lat, lon], skipna=True)
        mean.plot(ax=axes[1])
        axes[1].set_title(f"{args.var}: area mean (cos-lat weighted), {args.bbox}")
    fig.tight_layout()
    out = path.with_suffix(".png")
    fig.savefig(out, dpi=120)
    print(f"Saved {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("catalog", help="list NASA collections matching keywords")
    c.add_argument("--keyword", action="append", required=True, help="repeatable")
    c.add_argument("--start", type=int, default=1992)
    c.add_argument("--end", type=int, default=2022)
    c.add_argument("--bbox", default=ASIA_PACIFIC, help="west,south,east,north")
    c.add_argument("--limit", type=int, default=20)
    c.set_defaults(func=cmd_catalog)

    lo = sub.add_parser("local", help="summarise downloaded collections")
    lo.set_defaults(func=cmd_local)

    pl = sub.add_parser("plot", help="list variables in a file, or plot one")
    pl.add_argument("file")
    pl.add_argument("--var", default=None)
    pl.add_argument("--bbox", default=ASIA_PACIFIC, help="west,south,east,north")
    pl.set_defaults(func=cmd_plot)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
