"""POST /api/lineup: the case flow's LINEUP (noise lineup, checks, case verdict) from the engine."""

import math

import numpy as np
import pytest

from trend_detective.app.web import create_app

TREND_KEYS = {
    "region", "region_name", "variable", "label", "unit", "first_month", "last_month",
    "series", "annual", "band", "statistics", "sentence", "warnings", "significance", "lineup",
    "yearly",
}  # fmt: skip
YEARLY_KEYS = {
    "frequency", "first_year", "last_year", "series", "statistics", "band", "significance",
    "lineup", "warnings", "comparison",
}  # fmt: skip
LINEUP_KEYS = {
    "verdict", "headline", "explanation", "n_sims", "beat", "share", "observed_per_decade",
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


# --- the yearly block (ADR 0011) -----------------------------------------------------------------


def test_the_yearly_block_has_its_own_statistics_lineup_and_checks(client):
    y = post(client).get_json()["yearly"]
    assert set(y) == YEARLY_KEYS and y["frequency"] == "yearly"
    assert set(y["lineup"]) == LINEUP_KEYS and len(y["lineup"]["sims_per_decade"]) == 1000
    assert (y["first_year"], y["last_year"]) == (1992, 2016)
    assert len(y["series"]) == 25 and all(set(r) == {"year", "anomaly"} for r in y["series"])
    assert len(y["band"]) == 25 and set(y["band"][0]) == {"year", "fit", "low", "high"}
    assert set(y["significance"]) >= {"verdict", "ols_q", "mk_q", "sentence", "explanation"}


def test_the_yearly_slope_matches_the_monthly_slope_and_the_verdicts_agree_on_a_clear_trend(client):
    data = post(client).get_json()
    y = data["yearly"]
    assert y["statistics"]["ols_per_decade"] == pytest.approx(
        data["statistics"]["ols_per_decade"], abs=0.03
    )
    assert y["lineup"]["verdict"] == "detected" and y["lineup"]["beat"] == 0
    assert y["significance"]["verdict"] == "rise"
    assert "agree" in y["comparison"] and "a rise" in y["comparison"]
    assert data["lineup"]["verdict"] == "detected"  # the monthly block is as it was


def test_a_weak_trend_can_be_significant_monthly_but_not_yearly_and_the_sentence_says_why(client):
    found = None
    for seed in range(40):
        rng = np.random.default_rng(seed)
        vals, x = [], 0.0
        for i in range(300):
            x = 0.5 * x + rng.normal(0, 0.8)
            vals.append(round(10 * math.sin(2 * math.pi * (i % 12) / 12) + 0.3 / 120 * i + x, 5))
        data = post(client, values=vals).get_json()
        monthly_sig = data["significance"]["significant"]
        if monthly_sig and not data["yearly"]["significance"]["significant"]:
            found = data
            break
    assert found is not None, "expected at least one record that only the monthly view detects"
    text = found["yearly"]["comparison"]
    assert "independent values" in text and "25 yearly values" in text and "300 months" in text
    assert "differ in significance, not in the trend" in text
    assert "the monthly view has more power" in text or "about the same information" in text


def test_a_short_record_has_no_yearly_trend_and_says_so(client):
    y = post(client, values=months(30, 1.0)).get_json()["yearly"]  # 2.5 years: 2 full years
    assert y["lineup"]["verdict"] == "not_detected"
    assert y["lineup"]["n_sims"] is None and y["lineup"]["sims_per_decade"] == []
    assert "too few full years" in y["comparison"]


def test_yearly_values_need_ten_months_of_a_calendar_year(client):
    march = post(client, start="1992-03", values=months(300, 1.5, start_month=3)).get_json()
    april = post(client, start="1992-04", values=months(300, 1.5, start_month=4)).get_json()
    assert march["yearly"]["first_year"] == april["yearly"]["first_year"] == 1992
    assert march["yearly"]["series"][0]["anomaly"] is not None  # March to December: 10 months
    assert april["yearly"]["series"][0]["anomaly"] is None  # April to December: 9 months


def test_the_headline_is_in_both_views_and_agrees_with_the_verdict(client):
    data = post(client).get_json()
    assert data["lineup"]["headline"].startswith("Rising trend detected: about ")
    assert data["yearly"]["lineup"]["headline"].startswith("Rising trend detected: about ")
    short = post(client, values=months(72, 3.0)).get_json()
    assert short["lineup"]["headline"].startswith("No significant trend detected (yet): ")
    assert "years long" in short["lineup"]["headline"]
