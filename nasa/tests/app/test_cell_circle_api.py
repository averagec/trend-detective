"""POST /api/cell-circle: a circle drawn on the map, for the selected layer. Synthetic cells."""

import json
import os
from dataclasses import replace

import pytest

from trend_detective.app.web import create_app
from trend_detective.core.summary import Summary
from trend_detective.process.cell_circle import summary_to_record


def fake(ols_p, mk_p, slope=1.0):
    return Summary(
        n_months=312, n_years=26.0, ols_per_decade=slope, ols_ci_per_decade=(slope - 1, slope + 1),
        ols_p=ols_p, ols_significant=ols_p < 0.05, sen_per_decade=slope, mk_p=mk_p,
        mk_significant=mk_p < 0.05, tests_agree=True, warnings=(), sentence="",
        mk_p_ar1=mk_p, mk_ar1_significant=mk_p < 0.05,
    )  # fmt: skip


def write_cells(path, cells, layer="ssl", unit="mm"):
    records = [{**c, "summary": summary_to_record(c["summary"])} for c in cells]
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"layer": layer, "dataset": "TEST", "unit": unit, "period": [1992, 2017]}
    doc = {**meta, "cells": records}
    path.write_text(json.dumps(doc))


@pytest.fixture
def cells():
    """On the equator (1 degree is 111 km). Five cells that rise, each significant on its own, at
    longitude 100.00 to 100.20; sixty with no trend further east, 83 to 235 km from longitude 100.1.
    A 75 km circle at 100.1 holds only the five; a 250 km circle holds all 65."""
    rising = [
        {"k": i, "lat": 0.0, "lon": 100.0 + i * 0.05, "summary": fake(0.02, 0.02)}
        for i in range(5)
    ]
    flat = [
        {"k": 5 + i, "lat": 0.0, "lon": 100.85 + i * 0.025, "summary": fake(0.6, 0.6, 0.1)}
        for i in range(60)
    ]
    return rising + flat


@pytest.fixture
def client(tmp_path, cells):
    write_cells(tmp_path / "cell_stats" / "ssl.json", cells)
    stats_dir = tmp_path / "cell_stats"
    app = create_app(input_csv=tmp_path / "x.csv", images_dir=tmp_path, cell_stats_dir=stats_dir)
    return app.test_client()


def circle(client, lat=0.0, lon=100.1, radius_km=75, **extra):
    body = {"lat": lat, "lon": lon, "radius_km": radius_km, **extra}
    return client.post("/api/cell-circle", json=body)


def test_a_circle_returns_its_cells_and_a_verdict_for_each(client):
    r = circle(client)
    assert r.status_code == 200 and r.mimetype == "application/json"
    d = r.get_json()
    assert d["cells_inside"] == 5
    assert d["counts"] == {"rise": 5, "fall": 0, "unclear": 0, "none": 0, "no_data": 0}
    assert [c["k"] for c in d["cells"]] == [0, 1, 2, 3, 4]
    assert (d["layer"], d["dataset"], d["period"], d["unit"]) == ("ssl", "TEST", [1992, 2017], "mm")
    sig = d["cells"][0]["significance"]
    assert sig["family"] == {
        "name": "circle", "n_tests": 5, "method": "benjamini-hochberg", "alpha": 0.05,
    }  # fmt: skip
    assert sig["verdict"] == "rise" and "after correcting for 5 tests" in sig["sentence"]
    assert "centre inside the circle" in d["note"]
    assert b"NaN" not in r.data


def test_the_correction_follows_the_circle_you_draw(client):
    # the same five cells with the same p-values (0.02): a small circle holds only them ...
    small = circle(client, radius_km=75).get_json()
    assert small["cells_inside"] == 5 and small["counts"]["rise"] == 5
    assert small["cells"][0]["significance"]["ols_q"] == pytest.approx(0.02)
    # ... the largest circle also holds the sixty flat cells, so a family of 65: q = 0.02 x 65 / 5
    big = circle(client, radius_km=250).get_json()
    assert big["cells_inside"] == 65
    assert big["counts"]["rise"] == 0 and big["counts"]["none"] == 65
    first = big["cells"][0]["significance"]
    assert first["family"]["n_tests"] == 65 and first["ols_q"] == pytest.approx(0.26)
    assert first["verdict"] == "none"


def test_only_cells_with_their_centre_inside_are_included(client):
    # centred at 99.5, a 75 km circle reaches 72.3 km to the fourth cell and stops 2.8 km short of
    # the fifth cell's centre. That cell (about 55 km wide) overlaps the circle but is not in it.
    d = circle(client, lon=99.5, radius_km=75).get_json()
    assert d["cells_inside"] == 4 and [c["k"] for c in d["cells"]] == [0, 1, 2, 3]
    assert d["cells"][0]["significance"]["family"]["n_tests"] == 4
    # moved a little further, only three centres are inside: too few to say anything
    err = circle(client, lon=99.4, radius_km=75)
    assert err.status_code == 400 and "at least 4" in err.get_json()["error"]


def test_bad_requests_are_json_errors(client):
    assert circle(client, radius_km=50).get_json()["status"] == 400  # under 75 km
    assert circle(client, radius_km=251).status_code == 400  # over 250 km
    for body in ({"lat": "x", "lon": 100, "radius_km": 100}, {"lon": 100}, {}, [1, 2]):
        r = client.post("/api/cell-circle", json=body)
        assert r.status_code == 400 and set(r.get_json()) == {"error", "status"}
    not_json = client.post("/api/cell-circle", data="nope", content_type="application/json")
    assert not_json.status_code == 400
    assert circle(client, lat=95).status_code == 400
    assert circle(client, lon=500).status_code == 400
    for bad in ("nan", "inf"):
        body = {"lat": bad, "lon": 100, "radius_km": 100}
        assert client.post("/api/cell-circle", json=body).status_code == 400
    r = client.get("/api/cell-circle")
    assert r.status_code == 405 and "POST" in r.headers["Allow"]


def test_missing_cell_file_says_what_to_run(tmp_path):
    app = create_app(
        input_csv=tmp_path / "x.csv", images_dir=tmp_path, cell_stats_dir=tmp_path / "none"
    )
    r = app.test_client().post("/api/cell-circle", json={"lat": 0, "lon": 100, "radius_km": 100})
    assert r.status_code == 503 and "export_cells.py" in r.get_json()["error"]


def test_the_file_is_reread_when_it_changes(client, tmp_path, cells):
    # the store caches by modification time: a regenerated file is picked up without a restart
    assert circle(client).get_json()["counts"]["rise"] == 5
    falling = replace(fake(0.02, 0.02), ols_per_decade=-2.0, sen_per_decade=-2.0)
    changed = [{**c, "summary": falling} if c["k"] < 5 else c for c in cells]
    path = tmp_path / "cell_stats" / "ssl.json"
    write_cells(path, changed)
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))
    assert circle(client).get_json()["counts"]["fall"] == 5


# --- layers: the circle is read again for the selected layer -----------------------------------


def test_the_layer_picks_which_cells_are_judged(client, tmp_path, cells):
    falling = replace(fake(0.02, 0.02), ols_per_decade=-0.5, sen_per_decade=-0.5)
    other = [{**c, "summary": falling} if c["k"] < 5 else c for c in cells]
    write_cells(tmp_path / "cell_stats" / "t2m.json", other, layer="t2m", unit="degC")
    sea = circle(client).get_json()  # no layer given: sea level, as the page's first layer
    assert sea["layer"] == "ssl" and sea["counts"]["rise"] == 5
    temp = circle(client, layer="t2m").get_json()
    assert temp["layer"] == "t2m" and temp["unit"] == "degC" and temp["counts"]["fall"] == 5
    assert "degC per decade" in temp["cells"][0]["significance"]["sentence"]


def test_a_layer_without_a_file_says_what_it_needs(client):
    r = circle(client, layer="precip")
    err = assert_error(r, 503)
    assert "precip.json" in err and "export_cells.py" in err and "MERRA-2 cell cube" in err
    assert "GRACE" in assert_error(circle(client, layer="tws"), 503)


def test_a_layer_name_is_never_a_path(client):
    for bad in ("../ssl", "ssl/../ssl", "SSL", "a b", "", "x" * 21, 5, None, ["ssl"], "ssl.json"):
        r = circle(client, layer=bad)
        assert r.status_code == 400 and "layer must be a name" in r.get_json()["error"], bad


def assert_error(response, status):
    assert response.status_code == status and set(response.get_json()) == {"error", "status"}
    return response.get_json()["error"]
