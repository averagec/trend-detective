"""Tests for the flood and drought route (/api/event) and page (/event).

Uses a small synthetic cube and city list in a temporary folder. The NASA indicator files are
switched off for these tests, so the results depend only on the synthetic data.
"""

import numpy as np
import pytest

import trend_detective.process.event_series as event_series
from trend_detective.app.web import create_app
from trend_detective.process.cell_cube import Cube, write

LAT = -12.0 + 0.5 * np.arange(39)
LON = 94.375 + 0.625 * np.arange(77)
MONTHS = 24 * 12  # 1990-01 to 2013-12


def monthly(first_year: int, years: int) -> list[str]:
    return [f"{first_year + i // 12:04d}{i % 12 + 1:02d}" for i in range(12 * years)]


@pytest.fixture(autouse=True)
def no_indicator_files(monkeypatch, tmp_path):
    monkeypatch.setattr(event_series, "GEOJSON", tmp_path / "no_geojson")


@pytest.fixture
def paths(tmp_path):
    cubes = tmp_path / "cells"
    periods = monthly(1990, 24)
    rng = np.random.default_rng(7)
    rain = np.clip(3.0 + rng.normal(0, 0.4, (MONTHS, 39, 77)), 0.0, None)
    t2m = 295.0 + rng.normal(0, 0.5, (MONTHS, 39, 77))
    flood_month = 12 * 20 + 6  # July 2010
    rain[flood_month] += 9.0
    cube = Cube(
        lat=LAT,
        lon=LON,
        values={"precip": rain.astype(np.float32), "t2m": t2m.astype(np.float32)},
        periods={"precip": periods, "t2m": periods},
        manifest={
            "dataset": "merra2",
            "variables": {"precip": {"unit": "mm day-1"}, "t2m": {"unit": "K"}},
        },
    )
    write(cube, cubes)
    cities = tmp_path / "cities.csv"
    cities.write_text(
        "city_id,name,lat,lon,rainfall_source\n"
        "jkt,Central Jakarta,-6.1805,106.8280,merra2:precip\n"
        "gpc,Test city on GPCP,-6.1805,106.8280,gpcp:gpcp_precip\n",
        encoding="utf-8",
    )
    return {"cubes": cubes, "cities": cities, "tmp": tmp_path}


@pytest.fixture
def client(paths):
    app = create_app(
        input_csv=paths["tmp"] / "unused.csv",
        images_dir=paths["tmp"],
        cities_csv=paths["cities"],
        cubes_dir=paths["cubes"],
    )
    return app.test_client()


def test_cities_list_includes_the_rainfall_source(client):
    cities = client.get("/api/cities").get_json()["cities"]
    assert {c["id"]: c["rainfall_source"] for c in cities}["jkt"] == "merra2:precip"


def test_flood_month_returns_the_four_answers(client):
    resp = client.post(
        "/api/event",
        json={"incident": "flood", "city_id": "jkt",
              "period": {"type": "month", "year": 2010, "month": 7}},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["call"] in ("one_time_event", "extreme_in_trend", "not_unusual")
    assert body["where_when"]["cell"]["dataset"] == "merra2"
    assert body["where_when"]["peak"]["period"] == "2010-07"
    assert body["amount"]["extreme"] is True
    assert body["amount"]["amount_mm"] > 0
    assert body["period"]["label"] == "2010-07"


def test_co_movement_never_lists_the_rainfall_itself_and_says_not_a_cause(client):
    body = client.post(
        "/api/event",
        json={"incident": "flood", "city_id": "jkt",
              "period": {"type": "month", "year": 2010, "month": 7}},
    ).get_json()
    keys = [row["key"] for row in body["co_movement"]]
    assert "merra2:precip" not in keys
    assert "merra2:t2m" in keys
    assert all("not a cause" in row["note"] for row in body["co_movement"])


def test_drought_year_returns_twelve_months(client):
    body = client.post(
        "/api/event",
        json={"incident": "drought", "city_id": "jkt",
              "period": {"type": "year", "year": 2005}},
    ).get_json()
    assert body["period"]["kind"] == "year"
    assert len(body["where_when"]["months"]) == 12
    assert body["amount"]["unit"] == "mm"


def test_gpcp_city_without_a_gpcp_cube_is_a_503(client):
    resp = client.post(
        "/api/event",
        json={"incident": "flood", "city_id": "gpc",
              "period": {"type": "month", "year": 2010, "month": 7}},
    )
    assert resp.status_code == 503


@pytest.mark.parametrize(
    "payload, status",
    [
        ({"incident": "heatwave", "city_id": "jkt",
          "period": {"type": "month", "year": 2010, "month": 7}}, 400),
        ({"incident": "flood", "city_id": "nope",
          "period": {"type": "month", "year": 2010, "month": 7}}, 404),
        ({"incident": "flood", "city_id": "jkt",
          "period": {"type": "week", "year": 2010}}, 400),
        ({"incident": "flood", "city_id": "jkt",
          "period": {"type": "month", "year": 2010, "month": 13}}, 400),
        ({"incident": "flood", "city_id": "jkt",
          "period": {"type": "month", "year": 2100, "month": 1}}, 400),
        ({"incident": "flood", "city_id": "jkt", "period": {"type": "year", "year": "x"}}, 400),
    ],
)
def test_bad_event_requests_are_refused(client, payload, status):
    assert client.post("/api/event", json=payload).status_code == status


def test_event_page_is_served(client):
    resp = client.get("/event")
    assert resp.status_code == 200
    assert b"Flood or drought in a city" in resp.data
