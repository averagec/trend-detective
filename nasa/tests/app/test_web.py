"""Tests for the Flask app: the routes return what the analysis computes, for any window."""

import csv
import json
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


# --- JSON errors on every /api route ---------------------------------------------------------


def assert_json_error(response, status):
    assert response.status_code == status
    assert response.mimetype == "application/json"
    body = response.get_json()
    assert set(body) == {"error", "status"}
    assert body["status"] == status
    assert isinstance(body["error"], str) and body["error"]
    return body


@pytest.mark.parametrize(
    "query",
    [
        "from=abc",
        "to=1.5",
        "from=2000&to=1990",
        "from=0",
        "from=-5",
        "to=10000",
    ],
)
def test_bad_years_return_a_json_400(client, query):
    response = client.get(f"/api/trend?variable=t2m&region=east_asia_land&{query}")
    body = assert_json_error(response, 400)
    assert "year" in body["error"] or "before" in body["error"]


def test_unknown_region_or_variable_returns_a_json_404(client):
    body = assert_json_error(client.get("/api/trend?variable=t2m&region=nowhere"), 404)
    assert "nowhere" in body["error"]
    assert_json_error(client.get("/api/trend?variable=nothing&region=east_asia_land"), 404)
    assert_json_error(client.get("/api/trend"), 404)  # no parameters at all


def test_a_window_outside_the_record_returns_a_json_400(client):
    response = client.get("/api/trend?variable=t2m&region=east_asia_land&from=2500&to=2600")
    assert_json_error(response, 400)


def test_unknown_api_route_and_wrong_method_return_json(client):
    assert_json_error(client.get("/api/nothing-here"), 404)
    response = client.post("/api/meta")
    assert_json_error(response, 405)
    assert "GET" in response.headers["Allow"]


def test_pages_keep_the_normal_html_404(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert response.mimetype == "text/html"


def test_missing_data_error_has_the_same_shape(tmp_path):
    client = create_app(tmp_path / "absent.csv").test_client()
    assert_json_error(client.get("/api/meta"), 503)
    assert_json_error(client.get("/api/trend?variable=t2m&region=x"), 503)


def test_an_unexpected_error_is_json_and_leaks_nothing(csv_path, monkeypatch):
    app = create_app(csv_path)
    monkeypatch.setattr("trend_detective.app.web.build", lambda *a, **k: 1 / 0)
    response = app.test_client().get("/api/trend?variable=t2m&region=east_asia_land")
    body = assert_json_error(response, 500)
    assert "division" not in body["error"]


# --- The /api/trend response is frozen (docs/api.md) -------------------------------------------
# Adding a field means adding it here and in docs/api.md. Never rename or remove one: the page
# (app/static/app.js) and the static export depend on these names.

TREND_KEYS = {
    "region", "region_name", "variable", "label", "unit", "first_month", "last_month",
    "series", "annual", "band", "statistics", "sentence", "warnings",
}  # fmt: skip
STATISTICS_KEYS = {
    "n_months", "n_years", "ols_per_decade", "ols_ci_per_decade", "ols_p", "ols_significant",
    "sen_per_decade", "mk_p", "mk_significant", "tests_agree", "ols_intercept",
    "ols_slope_per_month", "n_eff", "r1", "mk_p_ar1", "mk_ar1_significant",
}  # fmt: skip


def test_trend_response_keys_are_frozen(client):
    data = client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()
    assert set(data) == TREND_KEYS
    assert set(data["statistics"]) == STATISTICS_KEYS
    assert set(data["series"][0]) == {"period", "value", "anomaly"}
    assert set(data["annual"][0]) == {"year", "mean_anomaly", "months"}
    assert set(data["band"][0]) == {"year", "fit", "low", "high"}


def test_trend_exposes_the_autocorrelation_adjustment(client):
    s = client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()["statistics"]
    assert 0.0 <= s["r1"] < 1.0
    assert 3.0 <= s["n_eff"] <= s["n_months"]
    assert s["n_eff"] == pytest.approx(
        max(s["n_months"] * (1 - s["r1"]) / (1 + s["r1"]), 3.0), rel=1e-9
    )
    assert s["ols_ci_per_decade"][0] < s["ols_per_decade"] < s["ols_ci_per_decade"][1]


def test_trend_response_is_valid_json_when_there_is_no_trend(client):
    # a one-year window has no statistics: NaN must be sent as null, never as the bare token NaN
    response = client.get("/api/trend?variable=t2m&region=east_asia_land&from=1990&to=1990")
    assert b"NaN" not in response.data and b"Infinity" not in response.data
    assert response.get_json()["statistics"]["n_eff"] is None


# --- POST /api/analyse ----------------------------------------------------------------------


def synthetic_months(n, slope_per_decade, start_month=1, noise=0.1, seed=5, amp=5.0):
    """Monthly values with a seasonal cycle on the real calendar month and a known trend."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        month = (start_month - 1 + i) % 12
        out.append(
            round(280 + amp * math.sin(2 * math.pi * month / 12)
                  + slope_per_decade / 120 * i + rng.normal(0, noise), 5)
        )  # fmt: skip
    return out


def body(**changes):
    base = {
        "label": "Test series",
        "unit": "K",
        "start": "1995-01",
        "values": synthetic_months(240, 0.30),
    }
    base.update(changes)
    return base


def test_analyse_returns_the_same_shape_as_trend(client):
    response = client.post("/api/analyse", json=body())
    assert response.status_code == 200
    data = response.get_json()
    assert set(data) == TREND_KEYS
    assert set(data["statistics"]) == STATISTICS_KEYS
    assert data["label"] == "Test series" and data["unit"] == "K"
    assert data["statistics"]["n_months"] == 240
    assert len(data["band"]) == 20


def test_analyse_recovers_a_known_slope_per_decade(client):
    # 0.30 K per decade, 20 years, small noise: both estimators must find it
    data = client.post("/api/analyse", json=body()).get_json()
    s = data["statistics"]
    assert s["ols_per_decade"] == pytest.approx(0.30, abs=0.03)
    assert s["ols_ci_per_decade"][0] < 0.30 < s["ols_ci_per_decade"][1]
    assert s["sen_per_decade"] == pytest.approx(0.30, abs=0.03)
    assert s["ols_significant"] is True
    assert "rose" in data["sentence"] and "statistically significant at 95%" in data["sentence"]
    assert "K per decade" in data["sentence"]


def test_analyse_recovers_a_known_negative_slope(client):
    values = synthetic_months(180, -0.50, seed=9)
    s = client.post("/api/analyse", json=body(values=values)).get_json()["statistics"]
    assert s["ols_per_decade"] == pytest.approx(-0.50, abs=0.04)


def test_analyse_with_no_trend_says_no_significant_trend(client):
    values = synthetic_months(240, 0.0, noise=1.0, seed=3)
    data = client.post("/api/analyse", json=body(values=values)).get_json()
    assert data["statistics"]["ols_significant"] is False
    assert "no significant trend detected (yet)" in data["sentence"]


def test_a_series_starting_mid_year_lands_on_its_real_calendar_months(client):
    values = synthetic_months(240, 0.30, start_month=3)
    data = client.post("/api/analyse", json=body(start="1995-03", values=values)).get_json()
    assert data["first_month"] == "1995-01"  # the axis always starts in January
    assert [row["value"] for row in data["series"][:2]] == [None, None]  # Jan, Feb: padding
    assert data["series"][2] == {
        "period": "1995-03",
        "value": values[0],
        "anomaly": data["series"][2]["anomaly"],
    }
    assert data["last_month"] == "2015-02"
    assert data["annual"][0] == {
        "year": 1995,
        "months": 10,
        "mean_anomaly": data["annual"][0]["mean_anomaly"],
    }
    assert data["band"][0]["year"] == 1995
    # the padding is not a gap in the record, so it must not trigger the missing-months warning
    assert not any("missing" in w for w in data["warnings"])


def test_a_short_series_starting_in_december_has_no_false_gap_warning(client):
    # 24 values from December: 11 padded months of 35 are 31% of the axis. They are padding,
    # not missing data, so the "months are missing" warning must not appear.
    values = synthetic_months(24, 0.30, start_month=12)
    data = client.post("/api/analyse", json=body(start="1995-12", values=values)).get_json()
    assert not any("missing" in w for w in data["warnings"])
    assert data["statistics"]["n_months"] == 24


def test_padding_does_not_change_the_statistics(client):
    # the same 240 values, said to start in January or in December: the trend is the same
    values = synthetic_months(240, 0.30)
    a = client.post("/api/analyse", json=body(values=values)).get_json()["statistics"]
    b = client.post("/api/analyse", json=body(start="1995-12", values=values)).get_json()
    for key in ("ols_per_decade", "ols_p", "sen_per_decade", "mk_p", "n_eff", "r1"):
        assert b["statistics"][key] == pytest.approx(a[key], rel=1e-9)


def test_analyse_with_gaps_counts_only_real_months(client):
    values = synthetic_months(240, 0.30)
    for i in range(5, 240, 7):  # about 14% of the months are missing
        values[i] = None
    data = client.post("/api/analyse", json=body(values=values)).get_json()
    n_missing = sum(v is None for v in values)
    assert data["statistics"]["n_months"] == 240 - n_missing
    assert any("missing" in w for w in data["warnings"])
    assert data["statistics"]["ols_per_decade"] == pytest.approx(0.30, abs=0.04)
    gap = data["series"][5]
    assert gap["value"] is None and gap["anomaly"] is None


@pytest.mark.xfail(
    strict=True,
    reason="core.trend.mann_kendall drops NaNs before computing Sen's slope, so with missing "
    "months it is per valid sample, not per month: 0.376 instead of 0.30 per decade (+25%) "
    "with 14% of months missing. OLS is unaffected. Remove this marker when it is fixed.",
)
def test_sen_slope_survives_gaps(client):
    values = synthetic_months(240, 0.30)
    for i in range(5, 240, 7):
        values[i] = None
    s = client.post("/api/analyse", json=body(values=values)).get_json()["statistics"]
    assert s["sen_per_decade"] == pytest.approx(0.30, abs=0.04)


def test_a_constant_series_is_handled(client):
    data = client.post("/api/analyse", json=body(values=[5.0] * 60)).get_json()
    assert data["statistics"]["ols_p"] == 1.0
    assert data["statistics"]["ols_significant"] is False


def test_analyse_works_without_the_data_file(tmp_path):
    client = create_app(tmp_path / "absent.csv").test_client()
    assert client.post("/api/analyse", json=body()).status_code == 200


def test_analyse_accepts_integers_and_a_label_with_markup_unchanged(client):
    data = client.post(
        "/api/analyse", json=body(label="<b>x</b> & y", values=list(range(60)))
    ).get_json()
    assert data["label"] == "<b>x</b> & y"  # the page escapes it when drawing
    assert data["statistics"]["ols_per_decade"] > 0


def test_too_short_series_is_refused(client):
    r = client.post("/api/analyse", json=body(values=synthetic_months(23, 0.3)))
    assert "24 to 2000" in assert_json_error(r, 400)["error"]
    r = client.post("/api/analyse", json=body(values=[]))
    assert_json_error(r, 400)


def test_a_series_with_too_few_real_numbers_is_refused(client):
    values = synthetic_months(40, 0.3)
    for i in range(20):
        values[i] = None  # 40 entries, 20 numbers
    r = client.post("/api/analyse", json=body(values=values))
    assert "at least 24 numbers" in assert_json_error(r, 400)["error"]


def test_too_long_series_is_refused(client):
    r = client.post("/api/analyse", json=body(values=[1.0] * 2001))
    assert "24 to 2000" in assert_json_error(r, 400)["error"]
    assert client.post("/api/analyse", json=body(values=[1.0] * 2000)).status_code == 200


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        ("not json at all", "JSON object"),
        ("", "JSON object"),
        ("[1, 2, 3]", "JSON object"),
        ('"text"', "JSON object"),
        ("null", "JSON object"),
        ("[" * 100000, "JSON object"),  # nested deeper than the parser allows
    ],
)
def test_malformed_bodies_are_refused(client, payload, fragment):
    r = client.post("/api/analyse", data=payload, content_type="application/json")
    assert fragment in assert_json_error(r, 400)["error"]


def test_a_body_that_is_not_declared_as_json_is_refused(client):
    r = client.post("/api/analyse", data=json.dumps(body()), content_type="text/plain")
    assert_json_error(r, 400)


@pytest.mark.parametrize("missing", ["label", "unit", "start", "values"])
def test_every_field_is_required(client, missing):
    payload = body()
    del payload[missing]
    r = client.post("/api/analyse", json=payload)
    assert missing in assert_json_error(r, 400)["error"]


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"label": ""}, "label"),
        ({"label": "   "}, "label"),
        ({"label": 5}, "label"),
        ({"label": None}, "label"),
        ({"label": "x" * 81}, "label"),
        ({"label": "two\nlines"}, "control"),
        ({"unit": ""}, "unit"),
        ({"unit": ["K"]}, "unit"),
        ({"unit": "x" * 21}, "unit"),
        ({"start": "1995-13"}, "start"),
        ({"start": "1995-00"}, "start"),
        ({"start": "0000-01"}, "start"),
        ({"start": "95-01"}, "start"),
        ({"start": "1995-1"}, "start"),
        ({"start": "1995-01-01"}, "start"),
        ({"start": "٣٣٣٣-٠١"}, "start"),  # non-ASCII digits
        ({"start": 199501}, "start"),
        ({"start": None}, "start"),
        ({"start": "9999-12"}, "9999"),  # runs past the year 9999
        ({"values": "1,2,3"}, "values"),
        ({"values": {"a": 1}}, "values"),
        ({"values": None}, "values"),
    ],
)
def test_bad_fields_are_refused_with_a_clear_message(client, changes, fragment):
    r = client.post("/api/analyse", json=body(**changes))
    assert fragment in assert_json_error(r, 400)["error"]


@pytest.mark.parametrize(
    "bad",
    ["1.5", "abc", True, False, [1], {"v": 1}, 1e13, -1e13],
)
def test_values_must_be_numbers_or_null(client, bad):
    values = synthetic_months(30, 0.3)
    values[7] = bad
    r = client.post("/api/analyse", json=body(values=values))
    assert "values[7]" in assert_json_error(r, 400)["error"]


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "1" + "0" * 400])
def test_non_finite_and_overflowing_numbers_are_refused(client, token):
    # Python's JSON parser accepts NaN and Infinity, and turns 1e999 into infinity
    values = json.dumps(synthetic_months(30, 0.3)[:-1] + [0]).replace("0]", token + "]")
    raw = '{"label": "x", "unit": "K", "start": "2000-01", "values": %s}' % values
    r = client.post("/api/analyse", data=raw, content_type="application/json")
    assert "values[29]" in assert_json_error(r, 400)["error"]


def test_an_oversize_body_is_refused_with_413(client):
    r = client.post("/api/analyse", json=body(label="x" * 200_000))
    assert_json_error(r, 413)


def test_analyse_only_accepts_post(client):
    r = client.get("/api/analyse")
    assert_json_error(r, 405)
    assert "POST" in r.headers["Allow"]


# --- GET /api/scan: all region x variable results with the multiple-testing correction -----------

# (region, variable, unit, slope per month, noise sd, seed). 20 years, 1990-2009. Three clear
# trends, one borderline series (p = 0.046 on its own) and five series with no trend.
SCAN_SPEC = [
    ("east_asia_land", "t2m", "K", 0.0025, 0.3, 1),
    ("east_asia_land", "precip", "mm day-1", 0.0020, 0.3, 2),
    ("east_asia_land", "evap", "mm day-1", 0.0004, 0.5, 46),  # borderline: p 0.046 alone
    ("se_asia_maritime", "t2m", "K", -0.0020, 0.3, 4),
    ("se_asia_maritime", "precip", "mm day-1", 0.0, 0.5, 44),
    ("se_asia_maritime", "evap", "mm day-1", 0.0, 0.5, 49),
    ("north_asia_siberia", "t2m", "K", 0.0, 0.5, 54),
    ("north_asia_siberia", "precip", "mm day-1", 0.0, 0.5, 55),
    ("north_asia_siberia", "evap", "mm day-1", 0.0, 0.5, 56),
]  # fmt: skip

SCAN_ROW_KEYS = {
    "region", "region_name", "variable", "label", "unit", "first_month", "last_month",
    "n_months", "n_years", "ols_per_decade", "ols_ci_per_decade", "ols_p", "ols_q",
    "significant_q", "ols_significant", "sen_per_decade", "mk_p", "mk_p_ar1", "n_eff",
    "tests_agree",
    "warnings",
}  # fmt: skip
SCAN_KEYS = {
    "from", "to", "method", "alpha", "n_tests", "n_significant_p", "n_significant_q", "note",
    "results",
}  # fmt: skip


@pytest.fixture
def scan_client(tmp_path: Path):
    path = tmp_path / "monthly_regional.csv"
    rows = []
    for region, variable, unit, slope, noise, seed in SCAN_SPEC:
        rng = np.random.default_rng(seed)
        for i in range(240):
            value = 280 + 3 * math.sin(2 * math.pi * i / 12) + slope * i + rng.normal(0, noise)
            rows.append(
                {
                    "region": region,
                    "variable": variable,
                    "period": f"{1990 + i // 12}-{i % 12 + 1:02d}",
                    "value": f"{value:.6g}",
                    "unit": unit,
                    "n_cells": 100,
                    "n_valid": 100,
                    "n_days": "",
                }
            )
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return create_app(path).test_client()


def test_scan_covers_every_region_and_variable(scan_client):
    data = scan_client.get("/api/scan").get_json()
    assert set(data) == SCAN_KEYS
    assert data["method"] == "benjamini-hochberg" and data["alpha"] == 0.05
    assert (data["from"], data["to"]) == (1990, 2009)
    keys = [(r["region"], r["variable"]) for r in data["results"]]
    assert keys == sorted((s[0], s[1]) for s in SCAN_SPEC)
    assert data["n_tests"] == 9
    for row in data["results"]:
        assert set(row) == SCAN_ROW_KEYS


def test_scan_q_values_are_benjamini_hochberg(scan_client):
    from scipy import stats

    rows = scan_client.get("/api/scan").get_json()["results"]
    p = np.array([r["ols_p"] for r in rows])
    q = np.array([r["ols_q"] for r in rows])
    np.testing.assert_allclose(q, stats.false_discovery_control(p, method="bh"), rtol=1e-9)
    assert np.all(q >= p) and np.all(q <= 1)


def test_scan_flags_significance_by_q_not_by_p(scan_client):
    data = scan_client.get("/api/scan").get_json()
    by_key = {(r["region"], r["variable"]): r for r in data["results"]}
    for key in [("east_asia_land", "t2m"), ("east_asia_land", "precip"),
                ("se_asia_maritime", "t2m")]:  # fmt: skip
        assert by_key[key]["significant_q"] is True and by_key[key]["ols_q"] < 0.01
    # the borderline series is significant on its own (p < 0.05) but not once the 9 tests are
    # accounted for: this is the false alarm the correction removes
    border = by_key[("east_asia_land", "evap")]
    assert border["ols_p"] < 0.05 and border["ols_significant"] is True
    assert border["ols_q"] >= 0.05 and border["significant_q"] is False
    assert data["n_significant_p"] == 4 and data["n_significant_q"] == 3
    for row in data["results"]:
        assert row["significant_q"] == (row["ols_q"] < 0.05)


def test_scan_trends_are_per_decade_in_native_units(scan_client):
    results = scan_client.get("/api/scan").get_json()["results"]
    rows = {(r["region"], r["variable"]): r for r in results}
    assert rows[("east_asia_land", "t2m")]["ols_per_decade"] == pytest.approx(0.30, abs=0.04)
    assert rows[("se_asia_maritime", "t2m")]["ols_per_decade"] == pytest.approx(-0.24, abs=0.04)
    assert rows[("east_asia_land", "t2m")]["unit"] == "K"
    assert rows[("east_asia_land", "precip")]["unit"] == "mm day-1"


def test_scan_agrees_with_trend_for_the_same_series(scan_client):
    row = next(
        r
        for r in scan_client.get("/api/scan?from=1995&to=2004").get_json()["results"]
        if (r["region"], r["variable"]) == ("east_asia_land", "t2m")
    )
    one = scan_client.get("/api/trend?variable=t2m&region=east_asia_land&from=1995&to=2004")
    stats = one.get_json()["statistics"]
    for key in ("ols_per_decade", "ols_p", "sen_per_decade", "mk_p", "n_eff", "n_months"):
        assert row[key] == pytest.approx(stats[key])


def test_scan_follows_the_year_window(scan_client):
    data = scan_client.get("/api/scan?from=2000&to=2009").get_json()
    assert (data["from"], data["to"]) == (2000, 2009)
    assert {r["n_months"] for r in data["results"]} == {120}
    assert data["results"][0]["first_month"] == "2000-01"


def test_scan_leaves_out_series_with_too_little_data_from_the_tests(scan_client):
    data = scan_client.get("/api/scan?from=2005&to=2005").get_json()  # one year: no statistics
    assert data["n_tests"] == 0
    for row in data["results"]:
        assert row["ols_p"] is None and row["ols_q"] is None and row["significant_q"] is False


def test_scan_refuses_bad_windows_with_json_errors(scan_client):
    for query in ("from=abc", "from=2009&to=1990", "to=10000", "from=2500&to=2600"):
        assert_json_error(scan_client.get(f"/api/scan?{query}"), 400)


def test_scan_without_data_says_what_to_run(tmp_path):
    client = create_app(tmp_path / "absent.csv").test_client()
    body = assert_json_error(client.get("/api/scan"), 503)
    assert "merra2_clean.py" in body["error"]


def test_scan_response_is_valid_json(scan_client):
    for query in ("", "?from=2005&to=2005"):
        raw = scan_client.get(f"/api/scan{query}").data
        assert b"NaN" not in raw and b"Infinity" not in raw


def test_both_mann_kendall_p_values_are_reported(client):
    s = client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()["statistics"]
    assert s["mk_p_ar1"] >= s["mk_p"]  # adjusting for autocorrelation never lowers the p-value
    assert s["mk_ar1_significant"] == (s["mk_p_ar1"] < 0.05)
    a = client.post("/api/analyse", json=body()).get_json()["statistics"]
    assert a["mk_p_ar1"] >= a["mk_p"]


# --- The website is served next to the API (web/dist), the plain page moves to /classic ----------


@pytest.fixture
def site_client(csv_path, tmp_path):
    site = tmp_path / "dist"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text("<title>TD-OS site</title>", encoding="utf-8")
    (site / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not public", encoding="utf-8")
    return create_app(csv_path, web_dir=site).test_client()


def test_the_site_is_served_at_the_root_with_its_files(site_client):
    assert b"TD-OS site" in site_client.get("/").data
    assert site_client.get("/assets/app.js").data == b"console.log(1)"
    assert site_client.get("/no-such-file.js").status_code == 404
    assert site_client.get("/no-such-file.js").mimetype == "text/html"


def test_the_plain_page_stays_at_classic(site_client):
    page = site_client.get("/classic")
    assert page.status_code == 200 and b"Trend Detective" in page.data
    assert b"TD-OS site" not in page.data
    assert site_client.get("/ocean").status_code == 200  # other pages are not shadowed


def test_the_api_is_not_shadowed_by_the_site(site_client):
    assert site_client.get("/api/meta").status_code == 200
    assert_json_error(site_client.get("/api/nothing-here"), 404)
    assert site_client.post("/api/analyse", json=body()).status_code == 200


def test_the_site_cannot_serve_files_outside_its_folder(site_client):
    for path in ("/../secret.txt", "/..%2fsecret.txt", "/assets/../../secret.txt"):
        response = site_client.get(path)
        assert response.status_code == 404 and b"not public" not in response.data


def test_without_a_build_the_plain_page_is_the_root(csv_path, tmp_path):
    for missing in (None, tmp_path / "not-built"):
        client = create_app(csv_path, web_dir=missing).test_client()
        assert b"Trend Detective" in client.get("/").data
        assert client.get("/classic").status_code == 200
        assert client.get("/assets/app.js").status_code == 404


# --- The website's fixtures (web/tests/fixtures) are real responses: keep them in step ------------

WEB_FIXTURES = Path(__file__).resolve().parents[2] / "web" / "tests" / "fixtures"


def same_shape(fixture, live):
    if isinstance(fixture, dict):
        return isinstance(live, dict) and fixture.keys() == live.keys() and all(
            same_shape(fixture[k], live[k]) for k in fixture
        )
    if isinstance(fixture, list):
        if not isinstance(live, list):
            return False
        return not fixture or not live or same_shape(fixture[0], live[0])
    return not isinstance(live, (dict, list))


def test_web_fixtures_have_the_shape_of_the_live_api(client, scan_client):
    # If this fails the API changed: regenerate web/tests/fixtures and re-run `npm test` in web/
    live = {
        "trend": client.get("/api/trend?variable=t2m&region=east_asia_land").get_json(),
        "scan": scan_client.get("/api/scan").get_json(),
        "analyse": client.post("/api/analyse", json=body()).get_json(),
    }
    for name, response in live.items():
        fixture = json.loads((WEB_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert same_shape(fixture, response), f"{name}: fixture and live response differ in shape"
