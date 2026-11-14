"""Tests for the Flask app: the routes return what the analysis computes, for any window."""

import csv
import math
from pathlib import Path

import numpy as np
import pytest

from trend_detective.app.web import create_app


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    rng = np.random.default_rng(11)
    path = tmp_path / "monthly_regional.csv"
    rows = []
    for region, slope in [("east_asia_land", 0.0012), ("se_asia_maritime", -0.0008)]:
        for i in range(12 * 31):  # 1980-01 to 2010-12
            year, month = 1980 + i // 12, i % 12 + 1
            value = 290 + 4 * math.sin(2 * math.pi * i / 12) + slope * i + rng.normal(0, 0.3)
            rows.append(
                {
                    "region": region,
                    "variable": "t2m",
                    "period": f"{year}-{month:02d}",
                    "value": f"{value:.6g}",
                    "unit": "K",
                    "n_cells": 100,
                    "n_valid": 100,
                    "n_days": "",
                }
            )
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def client(csv_path):
    return create_app(csv_path).test_client()


def test_meta_lists_the_variable_regions_and_years(client):
    meta = client.get("/api/meta").get_json()
    assert [v["key"] for v in meta["variables"]] == ["t2m"]
    assert meta["variables"][0]["unit"] == "K"
    assert {r["key"] for r in meta["regions"]} == {"east_asia_land", "se_asia_maritime"}
    assert meta["years"] == {"first": 1980, "last": 2010}


def test_trend_is_computed_for_the_whole_record(client):
    data = client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()
    assert len(data["series"]) == 12 * 31
    assert data["first_month"] == "1980-01"
    assert data["statistics"]["ols_significant"] is True
    assert data["statistics"]["ols_per_decade"] > 0
    assert "rose" in data["sentence"]


def test_a_year_window_changes_the_result(client):
    data = client.get("/api/trend?variable=t2m&region=east_asia_land&from=1990&to=1999").get_json()
    assert data["first_month"] == "1990-01"
    assert data["last_month"] == "1999-12"
    assert len(data["series"]) == 120
    assert data["statistics"]["n_years"] == pytest.approx(10.0)


def test_the_negative_region_falls(client):
    data = client.get("/api/trend?variable=t2m&region=se_asia_maritime").get_json()
    assert data["statistics"]["ols_per_decade"] < 0
    assert "fell" in data["sentence"]


def test_bad_requests_are_refused(client):
    assert (
        client.get("/api/trend?variable=t2m&region=east_asia_land&from=2000&to=1990").status_code
        == 400
    )
    assert client.get("/api/trend?variable=t2m&region=east_asia_land&from=abc").status_code == 400
    assert client.get("/api/trend?variable=t2m&region=nowhere").status_code == 404


def test_the_page_loads(client):
    page = client.get("/")
    assert page.status_code == 200
    assert b"Trend Detective" in page.data


def test_missing_data_says_what_to_run(tmp_path):
    client = create_app(tmp_path / "absent.csv").test_client()
    response = client.get("/api/meta")
    assert response.status_code == 503
    assert "merra2_clean.py" in response.get_json()["error"]


def test_trend_returns_a_95_percent_band_around_the_trend_line(client):
    data = client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()
    band = data["band"]
    assert [row["year"] for row in band] == list(range(1980, 2011))
    stats = data["statistics"]
    for i, row in enumerate(band):
        assert row["low"] < row["fit"] < row["high"]
        # the centre of the band is the plotted trend line (month index 12 * year offset + 6)
        line = stats["ols_intercept"] + stats["ols_slope_per_month"] * (12 * i + 6)
        assert row["fit"] == pytest.approx(line)
    assert "ols_band_by_year" not in stats  # sent once, as `band`


def test_band_follows_the_year_window(client):
    data = client.get("/api/trend?variable=t2m&region=east_asia_land&from=1990&to=1999").get_json()
    assert [row["year"] for row in data["band"]] == list(range(1990, 2000))
    wide = client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()["band"]
    narrow_width = data["band"][5]["high"] - data["band"][5]["low"]
    wide_width = wide[15]["high"] - wide[15]["low"]
    assert narrow_width > wide_width  # a shorter record leaves more doubt about the line


def test_band_is_empty_for_a_one_year_window(client):
    data = client.get("/api/trend?variable=t2m&region=east_asia_land&from=1990&to=1990").get_json()
    assert data["band"] == []
    assert data["statistics"]["ols_per_decade"] is None
