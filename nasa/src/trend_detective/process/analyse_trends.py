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
from trend_detective.core.significance import (  # noqa: E402
    ALPHA,
    Assessment,
    Item,
    assess_family,
    assess_single,
)
from trend_detective.core.summary import summarise  # noqa: E402
from trend_detective.core.trend import deseasonalize  # noqa: E402
from trend_detective.process.significance_json import significance_json  # noqa: E402

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


def window_values(
    entry: dict, first_year: int | None, last_year: int | None
) -> tuple[list[str], np.ndarray]:
    """The months of one series inside a year window, and their values (NaN where missing)."""
    axis = monthly_axis(list(entry["values"]), first_year, last_year)
    values = np.array([entry["values"].get(p, math.nan) for p in axis], dtype=float)
    return axis, values


def analyse_series(
    values: np.ndarray,
    axis: list[str],
    unit: str,
    summary_label: str,
    leading_pad: int = 0,
    assessment: Assessment | None = None,
) -> dict:
    """The part of the response that does not depend on where the series came from.

    `values` has one entry per month of `axis` and starts in January (NaN for missing months).
    `leading_pad` counts the NaN months at the front that only align the series to January.
    `assessment`: the verdict from a family of series (core/significance.py). Without one the
    series is judged on its own, with no correction.
    """
    summary = summarise(values, unit, summary_label, leading_pad=leading_pad)
    if assessment is None:
        assessment = assess_single(summary, summary_label, unit)
    anomalies = deseasonalize(values)
    return {
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
        "sentence": summary.sentence,  # this series alone, no correction: see `significance`
        "warnings": list(summary.warnings),
        "significance": significance_json(assessment),
    }


def build(
    region: str,
    variable: str,
    entry: dict,
    first_year: int | None = None,
    last_year: int | None = None,
    assessment: Assessment | None = None,
) -> dict:
    axis, values = window_values(entry, first_year, last_year)
    if not axis:
        raise ValueError(f"no months for {region} {variable} in {first_year}-{last_year}")
    label = LABELS.get(variable, variable)
    return {
        "region": region,
        "region_name": REGIONS[region].name,
        "variable": variable,
        "label": label,
        "unit": entry["unit"],
        **analyse_series(
            values, axis, entry["unit"], f"{label} in {REGIONS[region].name}", assessment=assessment
        ),
    }


def build_custom(
    label: str, unit: str, start_year: int, start_month: int, values: list[float | None]
) -> dict:
    """The same response as `build`, for a series the user supplies.

    `values` are consecutive months starting at `start_year`-`start_month`; None is a missing
    month. deseasonalize() assumes January first, so the front is padded with NaN until the first
    value sits on its real calendar month. The padded months appear in `series` with null values.
    """
    pad = start_month - 1
    padded = np.array(
        [math.nan] * pad + [math.nan if v is None else v for v in values], dtype=float
    )
    last = pad + len(values) - 1
    axis = monthly_axis([f"{start_year + last // 12:04d}-{last % 12 + 1:02d}"], start_year)
    return {
        "region": "custom",
        "region_name": "Your data",
        "variable": "custom",
        "label": label,
        "unit": unit,
        **analyse_series(padded, axis, unit, label, leading_pad=pad),
    }


def _layer_rows(series: dict, variable: str, first_year: int, last_year: int) -> list[tuple]:
    """(region, region name, label, unit, axis, summary, summary label) for one variable in every
    region that has months in the window, in region order."""
    rows = []
    for (region, var), entry in sorted(series.items()):
        if var != variable:
            continue
        axis, values = window_values(entry, first_year, last_year)
        if not axis:
            continue
        region_name = REGIONS[region].name if region in REGIONS else region
        label = LABELS.get(variable, variable)
        summary_label = f"{label} in {region_name}"
        s = summarise(values, entry["unit"], summary_label)
        rows.append((region, region_name, label, entry["unit"], axis, s, summary_label))
    return rows


def layer_assessments(
    series: dict, variable: str, first_year: int, last_year: int
) -> dict[str, Assessment]:
    """One variable across its regions, judged together: the "layer" family (ADR 0009)."""
    rows = _layer_rows(series, variable, first_year, last_year)
    if not rows:
        return {}
    items = [Item(r[5], r[6], r[3]) for r in rows]
    return {r[0]: a for r, a in zip(rows, assess_family(items, "layer"), strict=True)}


def scan(series: dict, variable: str, first_year: int, last_year: int) -> dict:
    """One variable in every region over one year window, judged as one family.

    Each region gets the same analysis as `build`. The OLS and the autocorrelation-adjusted
    Mann-Kendall p-values are each corrected across the regions (Benjamini-Hochberg), because
    testing several regions at 5% flags some by chance alone. A region is significant only when
    both tests are, after correction, and agree in sign (core/significance.py, ADR 0009).
    Regions with too little data have no p-value and are not counted as tests.
    """
    rows = _layer_rows(series, variable, first_year, last_year)
    if not rows:
        if not any(var == variable for _, var in series):
            raise KeyError(variable)
        raise ValueError(f"no months in {first_year}-{last_year}")
    assessed = assess_family([Item(r[5], r[6], r[3]) for r in rows], "layer")
    out = []
    for (region, region_name, label, unit, axis, s, _), a in zip(rows, assessed, strict=True):
        out.append(
            {
                "region": region,
                "region_name": region_name,
                "variable": variable,
                "label": label,
                "unit": unit,
                "first_month": axis[0],
                "last_month": axis[-1],
                "n_months": s.n_months,
                "n_years": s.n_years,
                "ols_per_decade": jsonable(s.ols_per_decade),
                "ols_ci_per_decade": [jsonable(x) for x in s.ols_ci_per_decade],
                "ols_p": jsonable(s.ols_p),
                "ols_q": jsonable(a.ols_q),
                "significant_q": a.significant,  # both tests, after correction
                "ols_significant": s.ols_significant,  # this region alone, p < 0.05
                "sen_per_decade": jsonable(s.sen_per_decade),
                "mk_p": jsonable(s.mk_p),
                "mk_p_ar1": jsonable(s.mk_p_ar1),
                "n_eff": jsonable(s.n_eff),
                "tests_agree": s.tests_agree,
                "warnings": list(s.warnings),
                "significance": significance_json(a),
            }
        )
    n_tests = assessed[0].n_tests
    return {
        "from": first_year,
        "to": last_year,
        "variable": variable,
        "family": "layer",
        "method": "benjamini-hochberg",
        "alpha": ALPHA,
        "n_tests": n_tests,
        "n_significant_p": sum(r["ols_significant"] for r in out),
        "n_significant_q": sum(r["significant_q"] for r in out),
        "note": (
            f"{n_tests} regions were tested together for this variable (Benjamini-Hochberg across "
            f"regions, false discovery rate). A trend counts as significant only when the OLS test "
            f"and the autocorrelation-adjusted Mann-Kendall test both have q below {ALPHA} and "
            "agree in sign."
        ),
        "results": out,
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
