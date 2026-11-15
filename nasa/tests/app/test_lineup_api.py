"""POST /api/lineup: the case flow's LINEUP (noise lineup, checks, case verdict) from the engine."""

import math

import numpy as np
import pytest

from trend_detective.app.web import create_app

TREND_KEYS = {
    "region", "region_name", "variable", "label", "unit", "first_month", "last_month",
    "series", "annual", "band", "statistics", "sentence", "warnings", "significance", "lineup",
}  # fmt: skip
LINEUP_KEYS = {
    "verdict", "explanation", "n_sims", "beat", "share", "observed_per_decade",
    "sims_per_decade", "checks", "years", "years_needed",
}  # fmt: skip
CHECK_KEYS = {"code", "text", "ok"}


@pytest.fixture
def client(tmp_path):
    # the data file is not needed: the series comes in the request, like /api/analyse-series
    return create_app(tmp_path / "absent.csv").test_client()


def months(n, per_decade, noise=0.4, seed=5, start_month=1):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        m = (start_month - 1 + i) % 12
        out.append(round(10 * math.sin(2 * math.pi * m / 12) + per_decade / 120 * i
                         + rng.normal(0, noise), 5))  # fmt: skip
    return out


def body(**changes):
    base = {"label": "Sea level, Jakarta", "unit": "mm", "start": "1992-01",
            "values": months(300, 1.5)}  # fmt: skip
    base.update(changes)
    return base


def post(client, **changes):
    return client.post("/api/lineup", json=body(**changes))


def test_lineup_has_the_trend_shape_plus_a_lineup_block(client):
    r = post(client)
    assert r.status_code == 200
    data = r.get_json()
    assert set(data) == TREND_KEYS
    assert set(data["lineup"]) == LINEUP_KEYS
    assert all(set(c) == CHECK_KEYS for c in data["lineup"]["checks"])
    assert data["lineup"]["n_sims"] == 1000 and len(data["lineup"]["sims_per_decade"]) == 1000


def test_a_clear_trend_is_detected_and_agrees_with_the_significance_block(client):
    data = post(client).get_json()
    lu = data["lineup"]
    assert lu["verdict"] == "detected" and lu["beat"] == 0
    assert data["significance"]["verdict"] == "rise"  # one verdict for one series
    assert lu["observed_per_decade"] == pytest.approx(data["statistics"]["ols_per_decade"])
    assert lu["observed_per_decade"] == pytest.approx(1.5, abs=0.3)
    assert all(c["ok"] for c in lu["checks"])
    assert "survives every check" in lu["explanation"]


def test_same_request_gives_the_same_answer(client):
    a = post(client).get_json()["lineup"]
    b = post(client).get_json()["lineup"]
    assert a == b


def test_a_short_record_is_not_detected_and_needs_ten_years(client):
    data = post(client, values=months(72, 3.0)).get_json()
    assert data["lineup"]["verdict"] == "not_detected"
    assert data["lineup"]["years_needed"] == 10.0
    assert {c["code"]: c["ok"] for c in data["lineup"]["checks"]}["record_length"] is False


def test_a_known_instrument_change_makes_a_clear_trend_suspect(client):
    data = post(client, start="2002-01", values=months(288, 1.5), gap_years=[2017, 2018]).get_json()
    assert data["lineup"]["verdict"] == "suspect"
    flags = {c["code"]: c["ok"] for c in data["lineup"]["checks"]}
    assert flags["instrument_change"] is False
    no_gap = post(client, start="2002-01", values=months(288, 1.5)).get_json()
    assert no_gap["lineup"]["verdict"] == "detected"


def test_the_least_data_the_statistics_accept_still_gets_an_answer(client):
    values = months(40, 1.0)
    for i in range(16):
        values[i] = None  # 24 numbers: the least the request check accepts
    r = post(client, values=values)
    assert r.status_code == 200
    assert r.get_json()["lineup"]["verdict"] == "not_detected"  # two years is under ten


BAD_GAPS = ["2017-2018", [2017], [2018, 2017], [2017.5, 2018], [True, 2018], [0, 5]]


@pytest.mark.parametrize("gap", BAD_GAPS)
def test_bad_gap_years_are_refused(client, gap):
    r = post(client, gap_years=gap)
    assert r.status_code == 400 and r.mimetype == "application/json"
    assert "gap_years" in r.get_json()["error"]


def test_series_rules_are_the_same_as_analyse_series(client):
    assert post(client, values=months(23, 0.3)).status_code == 400
    assert post(client, start="1992-13").status_code == 400
    assert client.post("/api/lineup", data="nope").status_code in (400, 415)
