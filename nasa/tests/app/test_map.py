"""Tests for the selection routes: city and circle analysis, validation and error responses.

Uses a small synthetic cube and city list in a temporary folder, so the tests run offline.
"""

import numpy as np
import pytest

from trend_detective.app.web import create_app
from trend_detective.process.cell_cube import Cube, write

LAT = -12.0 + 0.5 * np.arange(39)
LON = 94.375 + 0.625 * np.arange(77)


def monthly(first_year: int, years: int) -> list[str]:
    return [f"{first_year + i // 12:04d}{i % 12 + 1:02d}" for i in range(12 * years)]


@pytest.fixture
def paths(tmp_path):
    cubes = tmp_path / "cells"
    periods = monthly(1990, 24)
    rng = np.random.default_rng(5)
    t = np.arange(len(periods), dtype=float)[:, None, None]
    values = (290 + 0.002 * t + rng.normal(0, 0.3, (len(periods), 39, 77))).astype(np.float32)
    cube = Cube(
        lat=LAT,
        lon=LON,
        values={"t2m": values},
        periods={"t2m": periods},
        manifest={"dataset": "merra2", "variables": {"t2m": {"unit": "K"}}},
    )
    write(cube, cubes)
    cities = tmp_path / "cities.csv"
    cities.write_text(
        "city_id,name,lat,lon,rainfall_source\n"
        "jkt,Central Jakarta,-6.1805,106.8280,merra2:precip\n",
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


def test_city_list_is_returned(client):
    body = client.get("/api/cities").get_json()
    assert body["cities"] == [
        {
            "id": "jkt",
            "name": "Central Jakarta",
            "lat": -6.1805,
            "lon": 106.828,
            "rainfall_source": "merra2:precip",
        }
    ]


def test_missing_city_file_is_a_503(paths):
    app = create_app(
        input_csv=paths["tmp"] / "unused.csv",
        images_dir=paths["tmp"],
        cities_csv=paths["tmp"] / "nope.csv",
        cubes_dir=paths["cubes"],
    )
    assert app.test_client().get("/api/cities").status_code == 503


def test_city_cell_is_reported_per_dataset(client):
    body = client.get("/api/cell?city=jkt").get_json()
    assert body["cells"][0]["dataset"] == "merra2"
    assert body["cells"][0]["lat"] == pytest.approx(-6.0)
    assert body["cells"][0]["lon"] == pytest.approx(106.875)


def test_city_analysis_returns_series_summary_and_scale_warning(client):
    resp = client.post(
        "/api/analyse",
        json={"mode": "city", "city_id": "jkt", "variables": ["merra2:t2m"]},
    )
    assert resp.status_code == 200
    result = resp.get_json()["results"][0]
    assert result["cell"]["dataset"] == "merra2"
    assert result["summary"]["ols_significant"] is True
    assert result["summary"]["ols_per_decade"] == pytest.approx(0.24, abs=0.05)
    assert any("one grid cell" in w for w in result["warnings"])
    assert len(result["series"]) == len(result["periods"]) == 24 * 12


def test_circle_analysis_returns_cells_agreement_and_average(client):
    resp = client.post(
        "/api/analyse",
        json={"mode": "circle", "lat": -6.1805, "lon": 106.828, "radius_km": 100,
              "variables": ["merra2:t2m"]},
    )
    assert resp.status_code == 200
    result = resp.get_json()["results"][0]
    assert result["cells_used"] >= 4
    assert result["agreement"]["rising"] == result["cells_used"]
    assert len(result["cells"]) == result["cells_used"]
    assert result["average"]["summary"]["ols_significant"] is True


def test_year_window_limits_the_months(client):
    body = client.post(
        "/api/analyse",
        json={"mode": "city", "city_id": "jkt", "variables": ["merra2:t2m"],
              "from": 1995, "to": 2000},
    ).get_json()
    result = body["results"][0]
    assert result["periods"][0] == "199501"
    assert result["periods"][-1] == "200012"
    assert result["summary"]["n_months"] == 72


def test_missing_months_come_back_as_null(client):
    body = client.post(
        "/api/analyse",
        json={"mode": "city", "city_id": "jkt", "variables": ["merra2:t2m"],
              "from": 1990, "to": 1990},
    ).get_json()
    assert len(body["results"][0]["series"]) == 12
    assert None not in body["results"][0]["series"]


@pytest.mark.parametrize("radius", [74, 251, 300])
def test_radius_outside_the_range_is_a_400(client, radius):
    resp = client.post(
        "/api/analyse",
        json={"mode": "circle", "lat": -6.18, "lon": 106.83, "radius_km": radius,
              "variables": ["merra2:t2m"]},
    )
    assert resp.status_code == 400
    assert "radius must be 75 to 250 km" in resp.get_json()["error"]


@pytest.mark.parametrize(
    "payload, status",
    [
        ({"mode": "city", "city_id": "nope", "variables": ["merra2:t2m"]}, 404),
        ({"mode": "city", "city_id": "jkt", "variables": ["merra2:nothing"]}, 404),
        ({"mode": "city", "city_id": "jkt", "variables": ["era5:t2m"]}, 400),
        ({"mode": "city", "city_id": "jkt", "variables": []}, 400),
        ({"mode": "river", "variables": ["merra2:t2m"]}, 400),
        ({"mode": "circle", "lon": 106.8, "radius_km": 100, "variables": ["merra2:t2m"]}, 400),
        (
            {
                "mode": "city",
                "city_id": "jkt",
                "variables": ["merra2:t2m"],
                "from": 2000,
                "to": 1990,
            },
            400,
        ),
    ],
)
def test_bad_requests_are_refused(client, payload, status):
    assert client.post("/api/analyse", json=payload).status_code == status


def test_analysis_without_a_cube_is_a_503(paths):
    app = create_app(
        input_csv=paths["tmp"] / "unused.csv",
        images_dir=paths["tmp"],
        cities_csv=paths["cities"],
        cubes_dir=paths["tmp"] / "empty",
    )
    resp = app.test_client().post(
        "/api/analyse",
        json={"mode": "city", "city_id": "jkt", "variables": ["merra2:t2m"]},
    )
    assert resp.status_code == 503
