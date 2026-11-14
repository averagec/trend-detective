"""Turn cleaned regional monthly series into trend summaries for the web app.

Owns: building one monthly series per region and variable (optionally for a year window),
calling core/summary.py, and writing the JSON export. The Flask app (app/web.py) calls
build() for each request. No statistics are computed here.

Inputs : data/processed/merra2/monthly_regional.csv   (from process/merra2_clean.py)
Outputs: data/processed/json/index.json                 every series, with its headline sentence
         data/processed/json/<region>/<variable>.json  one series: values, anomalies, statistics,
                                                       95% trend band per year

Examples:
    python src/trend_detective/process/analyse_trends.py
    python src/trend_detective/process/analyse_trends.py --input some/other.csv --out some/dir
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.catalog.regions import REGIONS  # noqa: E402
from trend_detective.catalog.variables import VARIABLES  # noqa: E402
from trend_detective.core.summary import summarise  # noqa: E402
from trend_detective.core.trend import deseasonalize  # noqa: E402

INPUT = ROOT / "data" / "processed" / "merra2" / "monthly_regional.csv"
OUT = ROOT / "data" / "processed" / "json"
LABELS = {key: v.label for key, v in VARIABLES.items()}


def load(path: Path) -> dict[tuple[str, str], dict]:
    """(region, variable) -> {"unit": str, "values": {"YYYY-MM": float or NaN}}."""
    series: dict[tuple[str, str], dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["region"], row["variable"])
            entry = series.setdefault(key, {"unit": row["unit"], "values": {}})
            value = float(row["value"]) if row["value"] else math.nan
            entry["values"][row["period"]] = value
    return series


def monthly_axis(
    periods: list[str], first_year: int | None = None, last_year: int | None = None
) -> list[str]:
    """Every month from January of the first year to the last period, in order.

    The axis always starts in January: deseasonalize() assumes that.
    """
    start_year = first_year if first_year is not None else int(min(periods)[:4])
    last = max(periods)
    if last_year is not None:
        last = min(last, f"{last_year:04d}-12")
    year, month = start_year, 1
    out: list[str] = []
    while f"{year:04d}-{month:02d}" <= last:
        out.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def jsonable(x):
    """NaN is not valid JSON: write it as null."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, (np.floating,)):
        return jsonable(float(x))
    return x


def annual_means(axis: list[str], anomalies: np.ndarray) -> list[dict]:
    """Mean anomaly per calendar year. A display aggregate for the chart, not a statistic."""
    by_year: dict[str, list[float]] = {}
    for period, a in zip(axis, anomalies, strict=True):
        if math.isfinite(a):
            by_year.setdefault(period[:4], []).append(float(a))
    return [
        {"year": int(y), "mean_anomaly": float(np.mean(v)), "months": len(v)}
        for y, v in sorted(by_year.items())
    ]


def band_rows(axis: list[str], summary) -> list[dict]:
    """The 95% band from core/summary.py, labelled with calendar years. Nothing is computed here."""
    first_year = int(axis[0][:4])
    return [
        {
            "year": first_year + k,
            "fit": jsonable(fit),
            "low": jsonable(low),
            "high": jsonable(high),
        }
        for k, fit, low, high in summary.ols_band_by_year
    ]


def build(
    region: str,
    variable: str,
    entry: dict,
    first_year: int | None = None,
    last_year: int | None = None,
) -> dict:
    axis = monthly_axis(list(entry["values"]), first_year, last_year)
    if not axis:
        raise ValueError(f"no months for {region} {variable} in {first_year}-{last_year}")
    values = np.array([entry["values"].get(p, math.nan) for p in axis], dtype=float)
    label = LABELS.get(variable, variable)
    summary = summarise(values, entry["unit"], f"{label} in {REGIONS[region].name}")
    anomalies = deseasonalize(values)
    return {
        "region": region,
        "region_name": REGIONS[region].name,
        "variable": variable,
        "label": label,
        "unit": entry["unit"],
        "first_month": axis[0],
        "last_month": axis[-1],
        "series": [
            {"period": p, "value": jsonable(v), "anomaly": jsonable(a)}
            for p, v, a in zip(axis, values, anomalies, strict=True)
        ],
        "annual": [
            {**row, "mean_anomaly": jsonable(row["mean_anomaly"])}
            for row in annual_means(axis, anomalies)
        ],
        # 95% band around the OLS line (same unit as the anomalies), one row per year
        "band": band_rows(axis, summary),
        "statistics": {
            k: jsonable(v) if not isinstance(v, tuple) else [jsonable(x) for x in v]
            for k, v in asdict(summary).items()
            if k not in ("sentence", "warnings", "ols_band_by_year")
        },
        "sentence": summary.sentence,
        "warnings": list(summary.warnings),
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--input", type=Path, default=INPUT)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    index = []
    for (region, variable), entry in sorted(load(args.input).items()):
        result = build(region, variable, entry)
        path = args.out / region / f"{variable}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        stats = result["statistics"]
        index.append(
            {
                "region": region,
                "region_name": result["region_name"],
                "variable": variable,
                "label": result["label"],
                "unit": result["unit"],
                "path": f"{region}/{variable}.json",
                "sentence": result["sentence"],
                "ols_per_decade": stats["ols_per_decade"],
                "ols_significant": stats["ols_significant"],
                "warnings": len(result["warnings"]),
            }
        )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Wrote {len(index)} series to {args.out}")


if __name__ == "__main__":
    main()
