"""Regional map numbers: one layer, one frequency, every region.

Owns: reading the regional CSVs, building a full monthly (or yearly) series per region,
calling core/summary.summarise, and applying Benjamini-Hochberg across regions
(core/trend.benjamini_hochberg), separately for the OLS and Mann-Kendall p-values.
No statistics here: every trend, CI, p-value and adjustment comes from core/.

Inputs (written by the processing scripts):
    data/processed/merra2/monthly_regional.csv   region, variable, period, value, unit,
                                                 n_cells, n_valid
    data/processed/witness/witness_regional.csv  dataset, region, variable, period, value, ...
    data/processed/ocean/ocean_regional.csv      dataset, region, variable, period, value, ...
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from trend_detective.catalog.regions import REGIONS
from trend_detective.catalog.scope import clamp
from trend_detective.catalog.variables import VARIABLES
from trend_detective.core.detect import noise_params, years_needed
from trend_detective.core.significance import Item, assess_family
from trend_detective.core.summary import summarise
from trend_detective.core.trend import benjamini_hochberg
from trend_detective.process.event_series import indicator_monthly
from trend_detective.process.frequency import to_yearly
from trend_detective.process.significance_json import significance_json

SCHEMA_VERSION = 1
FREQS = ("monthly", "yearly")
FILES = {
    "merra2": "merra2/monthly_regional.csv",
    "witness": "witness/witness_regional.csv",
    "ocean": "ocean/ocean_regional.csv",
}
# layer key -> (file, value of the dataset column or None, variable name in that file)
LAYERS = {
    "merra2:t2m": ("merra2", None, "t2m"),
    "merra2:precip": ("merra2", None, "precip"),
    "merra2:evap": ("merra2", None, "evap"),
    "merra2:vpd": ("merra2", None, "vpd"),
    "merra2:qv2m": ("merra2", None, "qv2m"),
    "merra2:tsurf": ("merra2", None, "tsurf"),
    "merra2:t2mmax": ("merra2", None, "t2mmax"),
    "gpcp:gpcp_precip": ("witness", "gpcp", "gpcp_precip"),
    "gldas:gldas_rain": ("witness", "gldas", "gldas_rain"),
    "gldas:gldas_sm_0_10cm": ("witness", "gldas", "gldas_sm_0_10cm"),
    "gldas:gldas_sm_10_40cm": ("witness", "gldas", "gldas_sm_10_40cm"),
    "gldas:gldas_sm_40_100cm": ("witness", "gldas", "gldas_sm_40_100cm"),
    "gldas:gldas_sm_100_200cm": ("witness", "gldas", "gldas_sm_100_200cm"),
    "grace:grace_lwe": ("witness", "grace", "grace_lwe"),
    "ocean:ecco_v4r4_05deg": ("ocean", "ecco_v4r4_05deg", "ssh"),
    # Climate indices: one series for the whole Pacific and Indian Ocean (region "global").
    "index:enso": ("index", None, "enso"),
    "index:iod": ("index", None, "iod"),
    "index:pdo": ("index", None, "pdo"),
}


def layer_label(layer: str) -> str:
    variable = LAYERS[layer][2]
    return VARIABLES[variable].label if variable in VARIABLES else variable


def _read(processed_dir: Path, layer: str) -> dict[str, list[dict]]:
    file_key, dataset, variable = LAYERS[layer]
    if file_key == "index":
        monthly = indicator_monthly(variable)  # YYYYMM -> mean; empty if the file is missing
        rows = [
            {"region": "global", "period": f"{p[:4]}-{p[4:]}", "value": str(v), "unit": "index",
             "n_cells": "1", "n_valid": "1"}
            for p, v in sorted(monthly.items())
        ]
        return {"global": rows} if rows else {}
    path = Path(processed_dir) / FILES[file_key]
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run the processing script for it first.")
    out: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["variable"] != variable:
                continue
            if dataset is not None and row.get("dataset") != dataset:
                continue
            out.setdefault(row["region"], []).append(row)
    return out


def _float(text: str) -> float:
    return float(text) if text not in ("", None) else math.nan


def _month_axis(start_year: int, last_period: str) -> list[str]:
    """Every month from January of start_year up to last_period, in order."""
    out: list[str] = []
    year, month = start_year, 1
    while f"{year:04d}-{month:02d}" <= last_period:
        out.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def _code(text: str) -> str:
    if text.startswith("Only"):
        return "short_record"
    if "missing" in text:
        return "missing_months"
    if "tests disagree" in text:
        return "tests_disagree"
    if "not enough data" in text:
        return "not_enough_data"
    return "note"


def _no_data(key: str, name: str, text: str) -> dict:
    return {
        "key": key,
        "name": name,
        "status": "no_data",
        "warnings": [{"code": "no_data", "text": text}],
    }


def _region(
    key: str,
    rows: list[dict],
    layer: str,
    freq: str,
    first: int | None,
    last: int | None,
) -> dict:
    name = REGIONS[key].name if key in REGIONS else ("Global" if key == "global" else key)
    if not rows:
        return _no_data(key, name, f"No {name} data for this layer.")
    rows = [
        r
        for r in rows
        if (first is None or int(r["period"][:4]) >= first)
        and (last is None or int(r["period"][:4]) <= last)
    ]
    if not rows:
        return _no_data(key, name, "No months for this layer in the chosen years.")
    rows.sort(key=lambda r: r["period"])
    unit = rows[0]["unit"]
    label = f"{layer_label(layer)}, {name}"

    start_year = first if first is not None else int(rows[0]["period"][:4])
    axis = _month_axis(start_year, rows[-1]["period"])
    index = {p: i for i, p in enumerate(axis)}
    monthly = np.full(len(axis), math.nan)
    for r in rows:
        monthly[index[r["period"]]] = _float(r["value"])

    if not np.isfinite(monthly).any():  # e.g. ocean cells in a land-only box: nothing to test
        return _no_data(key, name, f"No valid {name} values for this layer.")

    def lead(values: np.ndarray) -> int:
        """Steps before the dataset begins. The timeline opens with the project window (1980), but
        GPCP starts in 1983 and GRACE in 2002: those steps are padding, not missing data."""
        return int(np.flatnonzero(np.isfinite(values))[0])

    if freq == "yearly":
        years, annual = to_yearly(axis, monthly)  # every year in the axis, NaN when incomplete
        span = [str(y) for y in years]
        pad = lead(annual) if np.isfinite(annual).any() else 0
        summary = summarise(annual, unit, label, steps_per_year=1, leading_pad=pad)
        n_units = len(years) - pad
    else:
        span = axis
        pad = lead(monthly)
        summary = summarise(monthly, unit, label, leading_pad=pad)
        n_units = len(axis) - pad

    n_cells = [int(float(r["n_cells"])) for r in rows if r["n_cells"]]
    n_valid = [int(float(r["n_valid"])) for r in rows if r["n_valid"]]
    ci_low, ci_high = summary.ols_ci_per_decade
    steps = 1 if freq == "yearly" else 12
    sigma, phi = noise_params(annual if freq == "yearly" else monthly, steps)
    needed = years_needed(summary.ols_per_decade, sigma, phi, steps_per_year=steps)
    return {
        "key": key,
        "name": name,
        "status": "ok",
        "unit": unit,
        "first_period": span[0],
        "last_period": span[-1],
        "n_points": summary.n_months,
        "n_years": round(summary.n_years, 2),
        # Simulation estimate: years for a 90% chance to detect this trend (core/detect.py).
        "years_needed_90": needed,
        "noise_sd": sigma,
        "noise_lag1": phi,
        "missing_share": 1 - summary.n_months / n_units,
        "cells_in_box": max(n_cells) if n_cells else None,
        "cells_valid_median": float(np.median(n_valid)) if n_valid else None,
        "slope_per_decade": summary.ols_per_decade,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "ols_p": summary.ols_p,
        "sen_per_decade": summary.sen_per_decade,
        "mk_p": summary.mk_p,
        "tests_agree": summary.tests_agree,
        "sentence": summary.sentence,  # this region alone, no correction: see `significance`
        "warnings": [{"code": _code(w), "text": w} for w in summary.warnings],
        "_summary": summary,  # handed to core/significance.py by build_map, then removed
        "_label": label,
    }


def _clean(obj):
    """NaN and infinity are not valid JSON: write them as null."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj) if math.isfinite(float(obj)) else None
    return obj


def build_map(
    processed_dir: Path,
    layer: str,
    freq: str = "monthly",
    first: int | None = None,
    last: int | None = None,
    regions: list[str] | None = None,
) -> dict:
    """Trend numbers for one layer in every region. Raises KeyError for an unknown layer and
    ValueError for a bad frequency, years or region."""
    if layer not in LAYERS:
        raise KeyError(layer)
    if freq not in FREQS:
        raise ValueError("freq must be 'monthly' or 'yearly'")
    first, last = clamp(first, last)  # the project window: 1980 to 2018
    if regions is not None:
        unknown = [r for r in regions if r not in REGIONS and r != "global"]
        if unknown:
            raise ValueError(f"unknown region(s): {', '.join(unknown)}")

    by_region = _read(processed_dir, layer)
    default = [k for k in REGIONS if k in by_region] + [k for k in by_region if k not in REGIONS]
    keys = regions if regions is not None else default
    results = [_region(k, by_region.get(k, []), layer, freq, first, last) for k in keys]

    ok = [i for i, r in enumerate(results) if r["status"] == "ok"]
    if ok:
        # The regions of one layer are one family (ADR 0009): core/significance.py corrects the OLS
        # and the autocorrelation-adjusted Mann-Kendall p-values and decides the direction.
        verdicts = assess_family(
            [Item(results[i]["_summary"], results[i]["_label"], results[i]["unit"]) for i in ok],
            "layer",
        )
        # kept for compatibility: the unadjusted Mann-Kendall p-value, corrected
        mk_old = benjamini_hochberg([results[i]["mk_p"] for i in ok])
        for j, i in enumerate(ok):
            a = verdicts[j]
            results[i]["ols_p_adj"] = a.ols_q
            results[i]["mk_p_adj"] = float(mk_old[j])
            results[i]["mk_p_ar1"] = a.mk_p_ar1
            results[i]["mk_p_ar1_adj"] = a.mk_q
            results[i]["direction"] = "none" if a.verdict == "no_data" else a.verdict
            results[i]["significance"] = significance_json(a)
    for r in results:
        r.pop("_summary", None)
        r.pop("_label", None)

    unit = next((r["unit"] for r in results if r["status"] == "ok"), "")
    return _clean(
        {
            "schema_version": SCHEMA_VERSION,
            "layer": layer,
            "label": layer_label(layer),
            "unit": unit,
            "freq": freq,
            "from": first,
            "to": last,
            "adjustment": (
                "Benjamini-Hochberg across regions, applied separately to the OLS and to the "
                "autocorrelation-adjusted Mann-Kendall p-values. A region is rise or fall only "
                "when both are significant after correction and agree in sign."
            ),
            "regions": results,
        }
    )
