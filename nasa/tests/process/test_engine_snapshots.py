"""Freeze what the trend engine returns today, on seeded synthetic data (no files, offline).

Two sections, so a later change is reviewed rather than silent:
  numbers   - trends, confidence intervals and p-values. These must not change when the
              significance engine takes over (docs: exec-plans/active/significance-engine.md).
  decisions - counts of rising and falling cells, `direction`, sentences and warnings. The
              significance engine changes these on purpose (both tests after correction); the
              snapshot is regenerated then, and the diff in the commit shows exactly what moved.

Regenerate:  UPDATE_SNAPSHOTS=1 pytest tests/process/test_engine_snapshots.py
"""

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from trend_detective.process.regional_map import build_map
from trend_detective.process.selection import Grid, analyse_circle, analyse_city

SNAPSHOT = Path(__file__).resolve().parents[1] / "snapshots" / "engine.json"
GRID = Grid(lat=-12.0 + 0.5 * np.arange(39), lon=94.375 + 0.625 * np.arange(77))
JAKARTA = (-6.1805357, 106.8280366)
YEARS = 24


def periods(first_year: int, years: int) -> list[str]:
    return [f"{first_year + i // 12:04d}{i % 12 + 1:02d}" for i in range(12 * years)]


def synthetic_cube() -> np.ndarray:
    """(months, lat, lon): flat noise everywhere, plus a rising and a falling patch near Jakarta."""
    rng = np.random.default_rng(11)
    n = 12 * YEARS
    t = np.arange(n, dtype=float)[:, None, None]
    slope = np.zeros((39, 77))
    slope[10:13, 18:22] = 0.004  # rising patch (about +0.48 K per decade)
    slope[13:16, 18:22] = -0.004  # falling patch
    season = 3.0 * np.sin(2 * np.pi * t / 12)
    return 290.0 + slope[None] * t + season + rng.normal(0, 0.4, (n, 39, 77))


def clean(x):
    """Plain JSON: NaN to None, numpy to python."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def summary_numbers(s) -> dict:
    return {
        "n_months": s.n_months,
        "n_years": s.n_years,
        "ols_per_decade": s.ols_per_decade,
        "ols_ci_per_decade": list(s.ols_ci_per_decade),
        "ols_p": s.ols_p,
        "sen_per_decade": s.sen_per_decade,
        "mk_p": s.mk_p,
        "tests_agree": s.tests_agree,
    }


def write_regional_csv(root: Path) -> None:
    rng = np.random.default_rng(23)
    lines = ["region,variable,period,value,unit,n_cells,n_valid,n_days"]
    for region, slope, noise in [
        ("east_asia_land", 0.0030, 0.5),  # clear rise
        ("se_asia_maritime", -0.0006, 0.5),  # weak fall
        ("north_asia_siberia", 0.0, 0.5),  # no trend
    ]:
        for i in range(12 * 15):
            p = f"{1990 + i // 12}-{i % 12 + 1:02d}"
            v = 280 + 4 * math.sin(2 * math.pi * i / 12) + slope * i + rng.normal(0, noise)
            lines.append(f"{region},t2m,{p},{v:.5f},K,10,10,")
    path = root / "merra2" / "monthly_regional.csv"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def payload(tmp_path: Path) -> dict:
    cube = synthetic_cube()
    pers = periods(1990, YEARS)
    city = analyse_city(cube, pers, GRID, *JAKARTA, "K", "T2M, Jakarta", "Jakarta")
    circle = analyse_circle(cube, pers, GRID, *JAKARTA, 150.0, "K", "T2M, circle")

    write_regional_csv(tmp_path)
    maps = {f: build_map(tmp_path, "merra2:t2m", freq=f) for f in ("monthly", "yearly")}

    numbers = {
        "city": {**summary_numbers(city.summary), "cell": [city.cell.lat, city.cell.lon]},
        "circle": {
            "cells_in_circle": circle.cells_in_circle,
            "cells_used": circle.cells_used,
            "expected_per_sign": circle.expected_per_sign,
            "slope_min": circle.slope_min,
            "slope_max": circle.slope_max,
            "cells": [
                {"lat": c.lat, "lon": c.lon, **summary_numbers(c.summary), "p_adj": c.p_adj}
                for c in circle.cells
            ],
            "average": summary_numbers(circle.average),
        },
        "map": {
            f: {
                r["key"]: {
                    k: r.get(k)
                    for k in (
                        "n_points", "slope_per_decade", "ci_low", "ci_high", "ols_p",
                        "sen_per_decade", "mk_p", "tests_agree", "ols_p_adj", "mk_p_adj",
                        "years_needed_90", "noise_sd", "noise_lag1",
                    )
                }
                for r in m["regions"]
            }
            for f, m in maps.items()
        },
    }
    decisions = {
        "city": {"sentence": city.summary.sentence, "warnings": list(city.warnings)},
        "circle": {
            "rising": circle.rising,
            "falling": circle.falling,
            "not_significant": circle.not_significant,
            "significant_cells": [c.significant for c in circle.cells],
            "warnings": list(circle.warnings),
        },
        "map": {
            f: {r["key"]: {"direction": r.get("direction"), "sentence": r.get("sentence")}
                for r in m["regions"]}
            for f, m in maps.items()
        },
    }
    return clean({"numbers": numbers, "decisions": decisions})


def close(a, b, path=""):
    """Equal structure, floats within a tight relative tolerance."""
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), f"{path}: keys differ"
        for k in a:
            close(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: length differs"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            close(x, y, f"{path}[{i}]")
    elif isinstance(a, float):
        assert b == pytest.approx(a, rel=1e-7, abs=1e-12), f"{path}: {a} vs {b}"
    else:
        assert a == b, f"{path}: {a!r} vs {b!r}"


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    data = payload(tmp_path_factory.mktemp("regional"))
    if os.environ.get("UPDATE_SNAPSHOTS"):
        SNAPSHOT.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    return data


def frozen():
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_trend_numbers_are_unchanged(now):
    close(frozen()["numbers"], now["numbers"])


def test_decisions_are_unchanged(now):
    close(frozen()["decisions"], now["decisions"])


def test_the_synthetic_case_exercises_the_engine(now):
    # a snapshot of nothing proves nothing: rising and falling cells, both frequencies, no NaN
    circle = now["decisions"]["circle"]
    assert circle["rising"] >= 3 and circle["falling"] >= 3
    assert set(now["numbers"]["map"]) == {"monthly", "yearly"}
    assert now["numbers"]["map"]["monthly"]["east_asia_land"]["slope_per_decade"] > 0.2
    assert now["numbers"]["circle"]["cells_used"] >= 10
