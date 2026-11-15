"""Flood and drought flow for one city: the page and the /api/event route.

Owns: the HTTP routes and the response shape. Statistics come from core/events.py and
core/comovement.py; the aligned monthly series come from process/event_series.py and
process/selection.py. The browser computes nothing.

Co-movement is reported as factors that moved together with rainfall. It is not a cause, and the
response says so for every factor.
"""

from __future__ import annotations

import math

import numpy as np
from flask import abort, render_template, request

from trend_detective.catalog.variables import VARIABLES
from trend_detective.core.comovement import comovement
from trend_detective.core.events import assess
from trend_detective.core.trend import deseasonalize
from trend_detective.process.cities import RAINFALL_SOURCES, load_cities
from trend_detective.process.event_series import (
    INDICATORS,
    align,
    days_per_month,
    indicator_series,
    month_span,
)
from trend_detective.process.selection import Grid, city_cell

RAINFALL_VARIABLES = {"merra2": "precip", "gpcp": "gpcp_precip"}
DATASET_NAMES = {"merra2": "MERRA-2", "gpcp": "GPCP"}
NOT_A_CAUSE = "Moved together with rainfall in the record. This is not a cause."


def _value(x):
    if isinstance(x, (list, tuple)):
        return [_value(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(float(x)) else None
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _cell_json(dataset: str, cell) -> dict:
    return {
        "dataset": dataset,
        "lat": cell.lat,
        "lon": cell.lon,
        "width_km": round(cell.width_km, 1),
        "height_km": round(cell.height_km, 1),
    }


def _parse_period(body: dict) -> tuple[str, int, int | None]:
    period = body.get("period")
    if not isinstance(period, dict):
        abort(400, description="period must be an object such as {type, year, month}")
    kind = period.get("type")
    if kind not in ("month", "year"):
        abort(400, description='period type must be "month" or "year"')
    try:
        year = int(period.get("year"))
    except (TypeError, ValueError):
        abort(400, description="period year must be a whole number")
    month = None
    if kind == "month":
        try:
            month = int(period.get("month"))
        except (TypeError, ValueError):
            abort(400, description="period month must be a whole number from 1 to 12")
        if not 1 <= month <= 12:
            abort(400, description="period month must be from 1 to 12")
    return kind, year, month


def _indices(full: list[str], kind: str, year: int, month: int | None) -> list[int]:
    wanted = (
        [f"{year:04d}{month:02d}"]
        if kind == "month"
        else [f"{year:04d}{m:02d}" for m in range(1, 13)]
    )
    position = {p: i for i, p in enumerate(full)}
    outside = [w for w in wanted if w not in position]
    if outside:
        abort(
            400,
            description=f"the period is outside the record ({full[0][:4]} to {full[-1][:4]})",
        )
    return [position[w] for w in wanted]


def _label(full: list[str], kind: str, year: int, month: int | None) -> str:
    return f"{year:04d}-{month:02d}" if kind == "month" else f"{year:04d}"


def _period_text(p: str) -> str:
    return f"{p[:4]}-{p[4:]}"


def register_event_routes(app, cubes, cities_path) -> None:
    @app.get("/event")
    def event_page():
        return render_template("event.html")

    @app.post("/api/event")
    def event():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400, description="send a JSON object")
        incident = body.get("incident")
        if incident not in ("flood", "drought"):
            abort(400, description='incident must be "flood" or "drought"')
        city_id = str(body.get("city_id", ""))
        match = [c for c in load_cities(cities_path) if c.city_id == city_id]
        if not match:
            abort(404, description=f"unknown city {city_id!r}")
        city = match[0]
        kind, year, month = _parse_period(body)

        rain_dataset, _, rain_var = city.rainfall_source.partition(":")
        rain_cube = cubes.get(rain_dataset)
        grid = Grid(rain_cube.lat, rain_cube.lon)
        cell = city_cell(grid, city.lat, city.lon)
        periods = rain_cube.periods[rain_var]
        full = month_span(periods[0], periods[-1])
        rate = align(periods, rain_cube.values[rain_var][:, cell.i, cell.j], full)
        totals = rate * days_per_month(full)
        indices = _indices(full, kind, year, month)
        try:
            result = assess(totals, rate, indices, incident, kind)
        except ValueError as err:
            abort(400, description=str(err))

        warnings = list(result.warnings)
        rain_anom = deseasonalize(rate)
        factors = []
        for dataset in cubes.available():
            cube = cubes.get(dataset)
            fgrid = Grid(cube.lat, cube.lon)
            fcell = city_cell(fgrid, city.lat, city.lon)
            rainfall_var = RAINFALL_VARIABLES[dataset]
            for var in cube.values:
                if var == rainfall_var:
                    continue
                series = align(cube.periods[var], cube.values[var][:, fcell.i, fcell.j], full)
                factors.append(
                    {
                        "key": f"{dataset}:{var}",
                        "label": VARIABLES[var].label if var in VARIABLES else var,
                        "source": f"{DATASET_NAMES[dataset]} grid cell",
                        "unit": cube.manifest.get("variables", {}).get(var, {}).get("unit", ""),
                        "series": series,
                    }
                )
        for name in INDICATORS:
            series = indicator_series(name, full)
            if np.isfinite(series).any():
                factors.append(
                    {
                        "key": name,
                        "label": VARIABLES[name].label,
                        "source": "NASA sea-surface height indicator",
                        "unit": "index as published",
                        "series": series,
                    }
                )

        co_movement = []
        for f in factors:
            try:
                res = comovement(rain_anom, deseasonalize(f["series"]), indices)
            except ValueError as err:
                warnings.append(f"{f['label']}: {err}")
                continue
            co_movement.append(
                {
                    "key": f["key"],
                    "label": f["label"],
                    "source": f["source"],
                    "unit": f["unit"],
                    "r": _value(res.r),
                    "p_value": _value(res.p_value),
                    "n": res.n,
                    "slope": _value(res.slope),
                    "period_anomaly": _value(res.period_anomaly),
                    "implied_rain_change": _value(res.implied_change),
                    "note": NOT_A_CAUSE,
                }
            )
        co_movement.sort(key=lambda row: -abs(row["r"]) if row["r"] is not None else 0.0)

        peak = result.peak
        return {
            "city": {
                "id": city.city_id,
                "name": city.name,
                "lat": city.lat,
                "lon": city.lon,
                "rainfall_source": city.rainfall_source,
                "rainfall_label": RAINFALL_SOURCES[city.rainfall_source],
            },
            "incident": incident,
            "period": {
                "kind": kind,
                "label": _label(full, kind, year, month),
            },
            "call": result.call,
            "sentence": result.sentence,
            "trend": {
                "slope_per_decade": _value(result.trend_slope_per_decade),
                "p_value": _value(result.trend_p_value),
                "direction": result.trend_direction,
                "unit": "mm/day",
            },
            "where_when": {
                "cell": _cell_json(rain_dataset, cell),
                "peak": None
                if peak is None
                else {
                    "period": _period_text(full[peak.index]),
                    "percentile": _value(peak.percentile),
                    "percent": _value(peak.percent),
                },
                "months": [
                    {
                        "period": _period_text(full[m.index]),
                        "total_mm": _value(m.total_mm),
                        "median_mm": _value(m.median_mm),
                        "percent": _value(m.percent),
                        "percentile": _value(m.percentile),
                    }
                    for m in result.months
                ],
            },
            "amount": {
                "observed_mm": _value(result.observed_mm),
                "median_mm": _value(result.median_mm),
                "amount_mm": _value(result.amount_mm),
                "percent": _value(result.percent),
                "percentile": _value(result.percentile),
                "extreme": result.extreme,
                "unit": "mm",
            },
            "co_movement": co_movement,
            "warnings": warnings,
        }
