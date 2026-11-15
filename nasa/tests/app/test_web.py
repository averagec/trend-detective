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
    "series", "annual", "band", "statistics", "sentence", "warnings", "significance",
}  # fmt: skip
SIGNIFICANCE_KEYS = {
    "family", "ols_p", "ols_q", "mk_p_ar1", "mk_q", "verdict", "significant", "expected_by_chance",
    "sentence", "warnings",
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


# --- POST /api/analyse-series ------------------------------------------------------------------


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
    response = client.post("/api/analyse-series", json=body())
    assert response.status_code == 200
    data = response.get_json()
    assert set(data) == TREND_KEYS
    assert set(data["statistics"]) == STATISTICS_KEYS
    assert data["label"] == "Test series" and data["unit"] == "K"
    assert data["statistics"]["n_months"] == 240
    assert len(data["band"]) == 20


def test_analyse_recovers_a_known_slope_per_decade(client):
    # 0.30 K per decade, 20 years, small noise: both estimators must find it
    data = client.post("/api/analyse-series", json=body()).get_json()
    s = data["statistics"]
    assert s["ols_per_decade"] == pytest.approx(0.30, abs=0.03)
    assert s["ols_ci_per_decade"][0] < 0.30 < s["ols_ci_per_decade"][1]
    assert s["sen_per_decade"] == pytest.approx(0.30, abs=0.03)
    assert s["ols_significant"] is True
    assert "rose" in data["sentence"] and "statistically significant at 95%" in data["sentence"]
    assert "K per decade" in data["sentence"]


def test_analyse_recovers_a_known_negative_slope(client):
    values = synthetic_months(180, -0.50, seed=9)
    s = client.post("/api/analyse-series", json=body(values=values)).get_json()["statistics"]
    assert s["ols_per_decade"] == pytest.approx(-0.50, abs=0.04)


def test_analyse_with_no_trend_says_no_significant_trend(client):
    values = synthetic_months(240, 0.0, noise=1.0, seed=3)
    data = client.post("/api/analyse-series", json=body(values=values)).get_json()
    assert data["statistics"]["ols_significant"] is False
    assert "no significant trend detected (yet)" in data["sentence"]


def test_a_series_starting_mid_year_lands_on_its_real_calendar_months(client):
    values = synthetic_months(240, 0.30, start_month=3)
    data = client.post("/api/analyse-series", json=body(start="1995-03", values=values)).get_json()
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
    data = client.post("/api/analyse-series", json=body(start="1995-12", values=values)).get_json()
    assert not any("missing" in w for w in data["warnings"])
    assert data["statistics"]["n_months"] == 24


def test_padding_does_not_change_the_statistics(client):
    # the same 240 values, said to start in January or in December: the trend is the same
    values = synthetic_months(240, 0.30)
    a = client.post("/api/analyse-series", json=body(values=values)).get_json()["statistics"]
    b = client.post("/api/analyse-series", json=body(start="1995-12", values=values)).get_json()
    for key in ("ols_per_decade", "ols_p", "sen_per_decade", "mk_p", "n_eff", "r1"):
        assert b["statistics"][key] == pytest.approx(a[key], rel=1e-9)


def test_analyse_with_gaps_counts_only_real_months(client):
    values = synthetic_months(240, 0.30)
    for i in range(5, 240, 7):  # about 14% of the months are missing
        values[i] = None
    data = client.post("/api/analyse-series", json=body(values=values)).get_json()
    n_missing = sum(v is None for v in values)
    assert data["statistics"]["n_months"] == 240 - n_missing
    assert any("missing" in w for w in data["warnings"])
    assert data["statistics"]["ols_per_decade"] == pytest.approx(0.30, abs=0.04)
    gap = data["series"][5]
    assert gap["value"] is None and gap["anomaly"] is None


def test_sen_slope_survives_gaps(client):
    # with missing months Sen's slope stays per month (the fix for gaps in mann_kendall)
    values = synthetic_months(240, 0.30)
    for i in range(5, 240, 7):
        values[i] = None
    s = client.post("/api/analyse-series", json=body(values=values)).get_json()["statistics"]
    assert s["sen_per_decade"] == pytest.approx(0.30, abs=0.04)


def test_a_constant_series_is_handled(client):
    data = client.post("/api/analyse-series", json=body(values=[5.0] * 60)).get_json()
    assert data["statistics"]["ols_p"] == 1.0
    assert data["statistics"]["ols_significant"] is False


def test_analyse_works_without_the_data_file(tmp_path):
    client = create_app(tmp_path / "absent.csv").test_client()
    assert client.post("/api/analyse-series", json=body()).status_code == 200


def test_analyse_accepts_integers_and_a_label_with_markup_unchanged(client):
    data = client.post(
        "/api/analyse-series", json=body(label="<b>x</b> & y", values=list(range(60)))
    ).get_json()
    assert data["label"] == "<b>x</b> & y"  # the page escapes it when drawing
    assert data["statistics"]["ols_per_decade"] > 0


def test_too_short_series_is_refused(client):
    r = client.post("/api/analyse-series", json=body(values=synthetic_months(23, 0.3)))
    assert "24 to 2000" in assert_json_error(r, 400)["error"]
    r = client.post("/api/analyse-series", json=body(values=[]))
    assert_json_error(r, 400)


def test_a_series_with_too_few_real_numbers_is_refused(client):
    values = synthetic_months(40, 0.3)
    for i in range(20):
        values[i] = None  # 40 entries, 20 numbers
    r = client.post("/api/analyse-series", json=body(values=values))
    assert "at least 24 numbers" in assert_json_error(r, 400)["error"]


def test_too_long_series_is_refused(client):
    r = client.post("/api/analyse-series", json=body(values=[1.0] * 2001))
    assert "24 to 2000" in assert_json_error(r, 400)["error"]
    assert client.post("/api/analyse-series", json=body(values=[1.0] * 2000)).status_code == 200


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
    r = client.post("/api/analyse-series", data=payload, content_type="application/json")
    assert fragment in assert_json_error(r, 400)["error"]


def test_a_body_that_is_not_declared_as_json_is_refused(client):
    r = client.post("/api/analyse-series", data=json.dumps(body()), content_type="text/plain")
    assert_json_error(r, 400)


@pytest.mark.parametrize("missing", ["label", "unit", "start", "values"])
def test_every_field_is_required(client, missing):
    payload = body()
    del payload[missing]
    r = client.post("/api/analyse-series", json=payload)
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
    r = client.post("/api/analyse-series", json=body(**changes))
    assert fragment in assert_json_error(r, 400)["error"]


@pytest.mark.parametrize(
    "bad",
    ["1.5", "abc", True, False, [1], {"v": 1}, 1e13, -1e13],
)
def test_values_must_be_numbers_or_null(client, bad):
    values = synthetic_months(30, 0.3)
    values[7] = bad
    r = client.post("/api/analyse-series", json=body(values=values))
    assert "values[7]" in assert_json_error(r, 400)["error"]


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "1" + "0" * 400])
def test_non_finite_and_overflowing_numbers_are_refused(client, token):
    # Python's JSON parser accepts NaN and Infinity, and turns 1e999 into infinity
    values = json.dumps(synthetic_months(30, 0.3)[:-1] + [0]).replace("0]", token + "]")
    raw = '{"label": "x", "unit": "K", "start": "2000-01", "values": %s}' % values
    r = client.post("/api/analyse-series", data=raw, content_type="application/json")
    assert "values[29]" in assert_json_error(r, 400)["error"]


def test_an_oversize_body_is_refused_with_413(client):
    r = client.post("/api/analyse-series", json=body(label="x" * 200_000))
    assert_json_error(r, 413)


def test_analyse_only_accepts_post(client):
    r = client.get("/api/analyse-series")
    assert_json_error(r, 405)
    assert "POST" in r.headers["Allow"]


# --- GET /api/scan: one variable across its regions, judged as one family (ADR 0009) ------------

# (region, variable, unit, slope per month, noise sd, seed). 20 years, 1990-2009. For t2m the family
# has 4 regions: a clear rise, a region significant on its own (OLS p 0.029, adjusted Mann-Kendall
# p 0.032) that is not significant after correcting for 4 regions, and two without a trend.
SCAN_SPEC = [
    ("east_asia_land", "t2m", "K", 0.0025, 0.3, 1),
    ("se_asia_maritime", "t2m", "K", 0.0005, 0.5, 340),  # borderline on its own
    ("north_asia_siberia", "t2m", "K", 0.0, 0.5, 54),
    ("extra_region", "t2m", "K", 0.0, 0.5, 55),
    ("east_asia_land", "precip", "mm day-1", -0.0020, 0.3, 2),  # a clear fall
    ("se_asia_maritime", "precip", "mm day-1", 0.0, 0.5, 44),
    ("north_asia_siberia", "precip", "mm day-1", 0.0, 0.5, 49),
]  # fmt: skip

SCAN_ROW_KEYS = {
    "region", "region_name", "variable", "label", "unit", "first_month", "last_month",
    "n_months", "n_years", "ols_per_decade", "ols_ci_per_decade", "ols_p", "ols_q",
    "significant_q", "ols_significant", "sen_per_decade", "mk_p", "mk_p_ar1", "n_eff",
    "tests_agree", "warnings", "significance",
}  # fmt: skip
SCAN_KEYS = {
    "from", "to", "variable", "family", "method", "alpha", "n_tests", "n_significant_p",
    "n_significant_q", "note", "results",
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


def scan_rows(client, query="variable=t2m"):
    data = client.get(f"/api/scan?{query}").get_json()
    return data, {r["region"]: r for r in data["results"]}


def test_scan_covers_the_regions_of_one_variable(scan_client):
    data, rows = scan_rows(scan_client)
    assert set(data) == SCAN_KEYS
    assert (data["variable"], data["family"]) == ("t2m", "layer")
    assert data["method"] == "benjamini-hochberg"
    assert (data["from"], data["to"], data["n_tests"]) == (1990, 2009, 4)
    assert sorted(rows) == [
        "east_asia_land", "extra_region", "north_asia_siberia", "se_asia_maritime",
    ]  # fmt: skip
    for row in rows.values():
        assert set(row) == SCAN_ROW_KEYS
        assert set(row["significance"]) == SIGNIFICANCE_KEYS
    precip = scan_client.get("/api/scan?variable=precip").get_json()
    assert precip["n_tests"] == 3  # another layer is another family


def test_scan_q_values_are_benjamini_hochberg_across_the_regions(scan_client):
    from scipy import stats

    _, rows = scan_rows(scan_client)
    order = sorted(rows)
    ols_p = np.array([rows[k]["ols_p"] for k in order])
    mk_p = np.array([rows[k]["mk_p_ar1"] for k in order])
    ols_q = np.array([rows[k]["significance"]["ols_q"] for k in order])
    mk_q = np.array([rows[k]["significance"]["mk_q"] for k in order])
    np.testing.assert_allclose(ols_q, stats.false_discovery_control(ols_p, method="bh"), rtol=1e-9)
    np.testing.assert_allclose(mk_q, stats.false_discovery_control(mk_p, method="bh"), rtol=1e-9)
    assert all(rows[k]["ols_q"] == rows[k]["significance"]["ols_q"] for k in order)


def test_a_region_significant_alone_is_not_significant_after_correction(scan_client):
    data, rows = scan_rows(scan_client)
    border = rows["se_asia_maritime"]
    assert border["ols_p"] < 0.05 and border["mk_p_ar1"] < 0.05  # on its own: both tests
    assert border["ols_significant"] is True
    sig = border["significance"]
    assert sig["ols_q"] > 0.05 and sig["mk_q"] > 0.05  # 0.029 x 4 / 2 and 0.032 x 4 / 2
    assert sig["verdict"] != "rise" and sig["significant"] is False
    assert border["significant_q"] is False
    assert "no significant trend detected (yet)" in sig["sentence"]
    assert data["n_significant_p"] > data["n_significant_q"]  # the correction removed a false alarm


def test_clear_trends_are_rise_and_fall_and_say_what_was_corrected(scan_client):
    _, rows = scan_rows(scan_client)
    rise = rows["east_asia_land"]["significance"]
    assert rise["verdict"] == "rise" and rise["significant"] is True
    assert rise["ols_q"] < 0.01 and rise["mk_q"] < 0.01
    assert rise["sentence"].endswith("significant at 95% after correcting for 4 tests at once.")
    assert rise["family"] == {
        "name": "layer", "n_tests": 4, "method": "benjamini-hochberg", "alpha": 0.05,
    }  # fmt: skip
    assert rise["expected_by_chance"] == pytest.approx(0.1)
    _, precip = scan_rows(scan_client, "variable=precip")
    assert precip["east_asia_land"]["significance"]["verdict"] == "fall"
    assert "fell by" in precip["east_asia_land"]["significance"]["sentence"]


def test_scan_trends_are_per_decade_in_native_units(scan_client):
    _, rows = scan_rows(scan_client)
    assert rows["east_asia_land"]["ols_per_decade"] == pytest.approx(0.30, abs=0.04)
    assert rows["east_asia_land"]["unit"] == "K"
    _, precip = scan_rows(scan_client, "variable=precip")
    assert precip["east_asia_land"]["ols_per_decade"] == pytest.approx(-0.24, abs=0.04)
    assert precip["east_asia_land"]["unit"] == "mm day-1"


def test_scan_agrees_with_trend_for_the_same_series(scan_client):
    _, rows = scan_rows(scan_client, "variable=t2m&from=1995&to=2004")
    url = "/api/trend?variable=t2m&region=east_asia_land&from=1995&to=2004"
    one = scan_client.get(url).get_json()
    row = rows["east_asia_land"]
    keys = ("ols_per_decade", "ols_p", "sen_per_decade", "mk_p", "mk_p_ar1", "n_eff", "n_months")
    for key in keys:
        assert row[key] == pytest.approx(one["statistics"][key])
    assert row["significance"] == one["significance"]  # the same block, from the same family


def test_trend_carries_the_verdict_of_its_layer_family(scan_client):
    data = scan_client.get("/api/trend?variable=t2m&region=se_asia_maritime").get_json()
    sig = data["significance"]
    assert set(sig) == SIGNIFICANCE_KEYS
    assert sig["family"]["name"] == "layer" and sig["family"]["n_tests"] == 4
    # the old per-series sentence stays (frozen) and still reads as significant on its own...
    assert "statistically significant at 95%" in data["sentence"]
    # ...while the block, which the page shows, accounts for the 4 regions tested
    assert "no significant trend detected (yet)" in sig["sentence"]
    assert sig["verdict"] != "rise"


def test_a_pasted_series_is_judged_on_its_own(client):
    data = client.post("/api/analyse-series", json=body()).get_json()
    sig = data["significance"]
    assert sig["family"] == {"name": "none", "n_tests": None, "method": None, "alpha": 0.05}
    assert sig["ols_q"] == sig["ols_p"] and sig["mk_q"] == sig["mk_p_ar1"]
    assert sig["verdict"] == "rise" and sig["expected_by_chance"] is None


def test_scan_follows_the_year_window(scan_client):
    data, rows = scan_rows(scan_client, "variable=t2m&from=2000&to=2009")
    assert (data["from"], data["to"]) == (2000, 2009)
    assert {r["n_months"] for r in rows.values()} == {120}
    assert rows["east_asia_land"]["first_month"] == "2000-01"


def test_scan_leaves_out_regions_with_too_little_data_from_the_tests(scan_client):
    data, rows = scan_rows(scan_client, "variable=t2m&from=2005&to=2005")  # one year: no statistics
    assert data["n_tests"] == 0
    for row in rows.values():
        assert row["ols_p"] is None and row["ols_q"] is None and row["significant_q"] is False
        assert row["significance"]["verdict"] == "no_data"


def test_scan_refuses_bad_requests_with_json_errors(scan_client):
    for query in (
        "variable=t2m&from=abc",
        "variable=t2m&from=2009&to=1990",
        "variable=t2m&to=10000",
        "variable=t2m&from=2500&to=2600",
        "",  # no variable
    ):
        assert_json_error(scan_client.get(f"/api/scan?{query}"), 400)
    assert_json_error(scan_client.get("/api/scan?variable=nothing"), 404)


def test_scan_without_data_says_what_to_run(tmp_path):
    client = create_app(tmp_path / "absent.csv").test_client()
    body_ = assert_json_error(client.get("/api/scan?variable=t2m"), 503)
    assert "merra2_clean.py" in body_["error"]


def test_scan_response_is_valid_json(scan_client):
    for query in ("variable=t2m", "variable=t2m&from=2005&to=2005"):
        raw = scan_client.get(f"/api/scan?{query}").data
        assert b"NaN" not in raw and b"Infinity" not in raw


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
        "scan": scan_client.get("/api/scan?variable=t2m").get_json(),
        "analyse": client.post("/api/analyse-series", json=body()).get_json(),
    }
    for name, response in live.items():
        fixture = json.loads((WEB_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert same_shape(fixture, response), f"{name}: fixture and live response differ in shape"


# --- The project window (catalog/scope.py: 1980 to 2018) applies to every route ------------------


@pytest.fixture
def wide_client(tmp_path: Path):
    """A record that runs past the window on both sides: 1975 to 2025."""
    rng = np.random.default_rng(8)
    path = tmp_path / "monthly_regional.csv"
    rows = []
    for region in ("east_asia_land", "se_asia_maritime"):
        for i in range(12 * 51):
            value = 290 + 3 * math.sin(2 * math.pi * i / 12) + 0.002 * i + rng.normal(0, 0.3)
            rows.append(
                {
                    "region": region,
                    "variable": "t2m",
                    "period": f"{1975 + i // 12}-{i % 12 + 1:02d}",
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
    return create_app(path).test_client()


def test_the_default_window_is_the_project_window(wide_client):
    assert wide_client.get("/api/meta").get_json()["years"] == {"first": 1980, "last": 2018}
    trend = wide_client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()
    assert (trend["first_month"], trend["last_month"]) == ("1980-01", "2018-12")
    assert trend["statistics"]["n_months"] == 12 * 39
    scan = wide_client.get("/api/scan?variable=t2m").get_json()
    assert (scan["from"], scan["to"]) == (1980, 2018)
    assert {r["last_month"] for r in scan["results"]} == {"2018-12"}


def test_requested_years_are_limited_to_the_window(wide_client):
    url = "/api/trend?variable=t2m&region=east_asia_land"
    wide = wide_client.get(f"{url}&from=1970&to=2000").get_json()
    assert (wide["first_month"], wide["last_month"]) == ("1980-01", "2000-12")
    late = wide_client.get(f"{url}&from=1990&to=2026").get_json()
    assert (late["first_month"], late["last_month"]) == ("1990-01", "2018-12")
    scan = wide_client.get("/api/scan?variable=t2m&from=1960&to=2030").get_json()
    assert (scan["from"], scan["to"]) == (1980, 2018)


def test_a_window_wholly_outside_the_project_is_refused_with_a_clear_message(wide_client):
    for query in ("from=1960&to=1975", "from=2019&to=2025"):
        for route in ("/api/trend?variable=t2m&region=east_asia_land", "/api/scan?variable=t2m"):
            err = assert_json_error(wide_client.get(f"{route}&{query}"), 400)
            assert "1980 to 2018" in err["error"]


def test_a_pasted_series_is_not_limited_to_the_project_window(client):
    # it is the user's own data: any years are analysed as sent
    data = client.post("/api/analyse-series", json=body(start="2021-01")).get_json()
    assert data["first_month"] == "2021-01" and data["last_month"] == "2040-12"
