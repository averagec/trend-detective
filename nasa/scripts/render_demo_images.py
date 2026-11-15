"""Render the two demo pictures for the ocean page: a sea-surface height map and the radar previews.

Owns: turning the raw ECCO grids and the Sentinel-1 browse previews into PNG files in
data/demo/images/, so the demo runs offline. Display only: the map is a plain average of the
valid monthly cells. No trend, p-value or significance is computed here; statistics come only
from core/trend.py.

Run from the repo root (needs matplotlib and h5py):
    python scripts/render_demo_images.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")  # no window needed; the files are written and the script exits
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trend_detective.catalog.sites import SITES  # noqa: E402

ECCO_DIR = ROOT / "data" / "raw" / "ocean" / "ECCO_L4_SSH_05DEG_MONTHLY_V4R4"
SAR_DIR = ROOT / "data" / "raw" / "sar"
OUT = ROOT / "data" / "demo" / "images"

FILL = 1.0e36  # PO.DAAC fill value is 9.96921e36
BOX = {"west": 95.0, "east": 141.0, "south": -11.0, "north": 28.0}  # Southeast Asia box
SITE_LABELS = {
    "singapore_east": "Singapore",
    "mekong_camau": "Ca Mau",
    "jakarta_north": "North Jakarta",
}
BACKGROUND = "#0b1b2b"
LAND = "#1b2a3a"
TEXT = "#e2e8f0"


def ok_rows(folder: Path) -> list[dict[str, str]]:
    with open(folder / "manifest.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("status") == "ok" and (folder / r["name"]).exists()]


def ocean_average(folder: Path):
    """Average SSH over every valid month, cell by cell, inside the box. Fill values are removed."""
    total = count = lat = lon = rows_ix = cols_ix = None
    years: list[str] = []
    for row in ok_rows(folder):
        with h5py.File(folder / row["name"], "r") as f:
            if lat is None:  # the grid is the same for every month: read it once
                lat_all = np.asarray(f["latitude"][:], dtype=float)
                lon_all = np.asarray(f["longitude"][:], dtype=float)
                rows_ix = np.where((lat_all >= BOX["south"]) & (lat_all <= BOX["north"]))[0]
                cols_ix = np.where((lon_all >= BOX["west"]) & (lon_all <= BOX["east"]))[0]
                lat, lon = lat_all[rows_ix], lon_all[cols_ix]
                total = np.zeros((len(rows_ix), len(cols_ix)))
                count = np.zeros_like(total)
            ssh = np.asarray(f["SSH"][0], dtype=float)[np.ix_(rows_ix, cols_ix)]
        ssh = np.where(np.abs(ssh) >= FILL, np.nan, ssh)
        valid = np.isfinite(ssh)
        total += np.where(valid, ssh, 0.0)
        count += valid
        years.append(row["time_start"][:4])
    if total is None:
        raise SystemExit(f"no usable ECCO files in {folder} (manifest status ok and present)")
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(count > 0, total / count, np.nan)
    return mean, lat, lon, len(years), min(years), max(years)


def style_axes(ax) -> None:
    ax.set_facecolor(LAND)
    ax.tick_params(colors=TEXT, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.set_xlabel("Longitude (°E)", color=TEXT)
    ax.set_ylabel("Latitude (°N)", color=TEXT)


def plot_ocean(mean, lat, lon, n: int, first: str, last: str, scenes: list, out: Path) -> None:
    # Show each cell against the box average, so the colours read as "above or below normal".
    anomaly = mean - np.nanmean(mean)
    limit = float(np.nanpercentile(np.abs(anomaly), 98))  # symmetric colour range, outliers clipped
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad(LAND)  # land and cells with no valid data

    fig, ax = plt.subplots(figsize=(10, 6.4), dpi=160, facecolor=BACKGROUND)
    style_axes(ax)
    half = 0.25  # the grid is 0.5 degrees, so the image edge is half a cell beyond the centres
    im = ax.imshow(
        np.ma.masked_invalid(anomaly),
        extent=[lon[0] - half, lon[-1] + half, lat[0] - half, lat[-1] + half],
        origin="lower",
        cmap=cmap,
        vmin=-limit,
        vmax=limit,
        interpolation="bilinear",
    )

    for i, feature in enumerate(scenes):
        xs, ys = zip(*feature["geometry"]["coordinates"][0], strict=True)
        ax.plot(
            xs,
            ys,
            color="#fde68a",
            linewidth=1.1,
            alpha=0.9,
            label="Radar scenes, 31 Mar 2024 (outlines)" if i == 0 else None,
        )

    for key, site in SITES.items():
        west, south, east, north = (float(v) for v in site.bbox.split(","))
        x, y = (west + east) / 2, (south + north) / 2
        ax.scatter(x, y, s=55, color="white", edgecolor=BACKGROUND, linewidth=1.2, zorder=5)
        ax.annotate(
            SITE_LABELS[key],
            (x, y),
            xytext=(9, 6),
            textcoords="offset points",
            color="white",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_xlim(BOX["west"], BOX["east"])
    ax.set_ylim(BOX["south"], BOX["north"])
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color="white", alpha=0.12, linewidth=0.6)
    ax.set_title(
        "Sea-surface height, Southeast Asia: above or below the box average",
        loc="left",
        color="white",
        fontsize=15,
        fontweight="bold",
        pad=12,
    )
    legend = ax.legend(loc="lower left", fontsize=9, frameon=False)
    for text in legend.get_texts():
        text.set_color("white")

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("metres: red = above the average, blue = below", color=TEXT)
    cbar.ax.tick_params(colors=TEXT, labelsize=9)
    cbar.outline.set_edgecolor("#334155")

    fig.text(
        0.01,
        0.01,
        f"Data: NASA ECCO ocean model, {n} monthly grids, {first} to {last}. Valid cells only. "
        "This is an average, not a trend.",
        color="#94a3b8",
        fontsize=8,
    )
    fig.savefig(out, facecolor=BACKGROUND, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_sar(rows: list[dict[str, str]], out: Path) -> None:
    cols = 3  # 2 rows of 3 keeps each preview large enough to read on a phone
    nrows = -(-len(rows) // cols)
    fig, axes = plt.subplots(nrows, cols, figsize=(10, 3.6 * nrows), dpi=130, facecolor=BACKGROUND)
    flat = np.atleast_1d(axes).ravel()
    for ax in flat:
        ax.axis("off")
    for ax, row in zip(flat, rows, strict=False):
        image = plt.imread(SAR_DIR / "browse" / f"{row['sceneName']}.jpg")
        ax.imshow(image, cmap="gray" if image.ndim == 2 else None)
        ax.set_title(row["startTime"][11:19] + " UTC", color=TEXT, fontsize=10)
    days = sorted({row["startTime"][:10] for row in rows})
    fig.suptitle(
        f"Radar previews: 5 of the 20 Sentinel-1 scenes from {days[0]}, near northern Sumatra",
        color="white",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )
    fig.text(
        0.01,
        0.01,
        "Data: ASF Sentinel-1 browse images (preview only, not measurements). "
        "These scenes do not cover the study sites. Outlines of all 20 scenes are on the map.",
        color="#94a3b8",
        fontsize=8,
    )
    fig.savefig(out, facecolor=BACKGROUND, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mean, lat, lon, n, first, last = ocean_average(ECCO_DIR)
    scenes = json.loads((SAR_DIR / "scenes.geojson").read_text(encoding="utf-8"))["features"]
    plot_ocean(mean, lat, lon, n, first, last, scenes, OUT / "ocean_ssh_mean.png")

    with open(SAR_DIR / "scenes.csv", newline="", encoding="utf-8") as f:
        scene_rows = list(csv.DictReader(f))
    rows = [r for r in scene_rows if (SAR_DIR / "browse" / f"{r['sceneName']}.jpg").exists()]
    if not rows:
        raise SystemExit("no SAR browse previews found in data/raw/sar/browse")
    plot_sar(sorted(rows, key=lambda r: r["startTime"]), OUT / "sar_browse_scenes.png")

    print(f"ocean: {n} monthly grids ({first}-{last}) -> {OUT / 'ocean_ssh_mean.png'}")
    print(f"sar: {len(rows)} previews -> {OUT / 'sar_browse_scenes.png'}")


if __name__ == "__main__":
    main()
