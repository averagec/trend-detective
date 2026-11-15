"""Tests for GET /api/map on synthetic regional CSVs (known trends, no real data)."""

import numpy as np
import pytest

from trend_detective.app.web import create_app

PERIODS = [f"{y}-{m:02d}" for y in range(1980, 2000) for m in range(1, 13)]  # 20 years


def _series(seed: int, slope_per_month: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(len(PERIODS))
    return 0.5 * np.sin(2 * np.pi * t / 12) + slope_per_month * t + rng.normal(0, 0.05, t.size)


@pytest.fixture
def client(tmp_path):
    # 0.05 K per year = 0.5 K per decade in the rising region; the other region has no trend.
    rising, flat = _series(1, 0.05 / 12), _series(2, 0.0)
    lines = ["region,variable,period,value,unit,n_cells,n_valid,n_days"]
    for region, values in (("se_asia_maritime", rising), ("east_asia_land", flat)):
        for period, value in zip(PERIODS, values, strict=True):
            lines.append(f"{region},t2m,{period},{value:.6f},K,100,100,")
    path = tmp_path / "merra2" / "monthly_regional.csv"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    app = create_app(input_csv=tmp_path / "none.csv", processed_dir=tmp_path)
    return app.test_client()


def _by_key(payload: dict) -> dict:
    return {r["key"]: r for r in payload["regions"]}


def test_rising_region_is_detected_and_flat_one_is_not(client):
    regions = _by_key(client.get("/api/map?variable=merra2:t2m").get_json())
    rising = regions["se_asia_maritime"]
    assert rising["slope_per_decade"] == pytest.approx(0.5, abs=0.05)
    assert rising["ols_p_adj"] < 0.05
    assert rising["direction"] == "rise"
    assert regions["east_asia_land"]["direction"] == "none"


def test_adjusted_p_values_are_never_below_the_raw_ones(client):
    for region in _by_key(client.get("/api/map?variable=merra2:t2m").get_json()).values():
        assert region["ols_p_adj"] >= region["ols_p"] - 1e-12
        assert region["mk_p_adj"] >= region["mk_p"] - 1e-12


def test_yearly_frequency_gives_annual_slope(client):
    payload = client.get("/api/map?variable=merra2:t2m&freq=yearly").get_json()
    rising = _by_key(payload)["se_asia_maritime"]
    assert payload["freq"] == "yearly"
    assert rising["n_points"] == 20
    assert rising["slope_per_decade"] == pytest.approx(0.5, abs=0.1)


def test_year_window_sets_the_first_and_last_period(client):
    rising = _by_key(client.get("/api/map?variable=merra2:t2m&from=1985&to=1994").get_json())[
        "se_asia_maritime"
    ]
    assert rising["first_period"] == "1985-01"
    assert rising["last_period"] == "1994-12"


def test_response_names_the_adjustment_and_unit(client):
    payload = client.get("/api/map?variable=merra2:t2m").get_json()
    assert "Benjamini-Hochberg" in payload["adjustment"]
    assert payload["unit"] == "K"


def test_unknown_variable_is_not_found(client):
    assert client.get("/api/map?variable=merra2:nope").status_code == 404


def test_bad_frequency_is_rejected(client):
    assert client.get("/api/map?variable=merra2:t2m&freq=weekly").status_code == 400


def test_unknown_region_is_rejected(client):
    assert client.get("/api/map?variable=merra2:t2m&regions=atlantis").status_code == 400
