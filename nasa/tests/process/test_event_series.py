"""Tests for the event inputs: month span, alignment, day counts, indicators and the city list."""

import json

import numpy as np
import pytest

import trend_detective.process.event_series as event_series
from trend_detective.process.cities import load_cities
from trend_detective.process.event_series import (
    align,
    days_per_month,
    indicator_monthly,
    month_span,
)


def test_month_span_crosses_the_year_boundary():
    assert month_span("199911", "200002") == ["199911", "199912", "200001", "200002"]


def test_align_puts_missing_months_as_nan():
    out = align(["199001", "199003"], np.array([1.0, 3.0]), ["199001", "199002", "199003"])
    assert out[0] == 1.0 and np.isnan(out[1]) and out[2] == 3.0


def test_days_per_month_knows_leap_years():
    days = days_per_month(["200002", "200102"])
    assert days.tolist() == [29.0, 28.0]


def test_indicator_monthly_averages_a_month(monkeypatch, tmp_path):
    def feature(dec, value):
        return {"type": "Feature", "properties": {"decimal_year": dec, "enso_index": value}}

    data = {"features": [feature(2000.0, 1.0), feature(2000.05, 3.0), feature(2000.5, -1.0)]}
    (tmp_path / "NASA_SSH_ENSO_INDICATOR.geojson").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(event_series, "GEOJSON", tmp_path)
    monthly = indicator_monthly("enso")
    assert monthly["200001"] == pytest.approx(2.0)
    assert monthly["200007"] == pytest.approx(-1.0)


def test_missing_indicator_file_gives_no_months(monkeypatch, tmp_path):
    monkeypatch.setattr(event_series, "GEOJSON", tmp_path)
    assert indicator_monthly("pdo") == {}


def test_city_list_checks_the_rainfall_source(tmp_path):
    good = tmp_path / "good.csv"
    good.write_text(
        "city_id,name,lat,lon,rainfall_source\nbdg,Bandung,-6.9175,107.6191,gpcp:gpcp_precip\n",
        encoding="utf-8",
    )
    assert load_cities(good)[0].rainfall_source == "gpcp:gpcp_precip"

    bad = tmp_path / "bad.csv"
    bad.write_text(
        "city_id,name,lat,lon,rainfall_source\nbdg,Bandung,-6.9175,107.6191,era5:tp\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="rainfall_source must be one of"):
        load_cities(bad)


def test_city_list_needs_the_rainfall_column(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text("city_id,name,lat,lon\nbdg,Bandung,-6.9175,107.6191\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rainfall_source"):
        load_cities(path)
