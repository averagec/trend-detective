"""A circle drawn on the sea-level map: the cells whose centre is inside it are corrected together
(process/ocean_circle.py, ADR 0009). Synthetic cells, offline."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

from trend_detective.core.summary import Summary, summarise
from trend_detective.process.ocean_circle import (
    OceanCells,
    analyse_circle,
    cells_inside,
    load,
    summary_from_record,
    summary_to_record,
)
from trend_detective.process.selection import SelectionError, haversine_km

KM_PER_DEG = 111.195  # the great-circle length of one degree of latitude


def fake(ols_p, mk_p, slope=1.0):
    """A cell's summary with chosen p-values (slopes per decade)."""
    return Summary(
        n_months=312, n_years=26.0, ols_per_decade=slope, ols_ci_per_decade=(slope - 1, slope + 1),
        ols_p=ols_p, ols_significant=ols_p < 0.05, sen_per_decade=slope, mk_p=mk_p,
        mk_significant=mk_p < 0.05, tests_agree=True, warnings=(), sentence="",
        mk_p_ar1=mk_p, mk_ar1_significant=mk_p < 0.05,
    )  # fmt: skip


def cells_at(points, summaries):
    """OceanCells from (lat, lon) points; k is the position in the list."""
    lat = np.array([p[0] for p in points], dtype=float)
    lon = np.array([p[1] for p in points], dtype=float)
    return OceanCells(
        k=np.arange(len(points)), lat=lat, lon=lon, summaries=list(summaries),
        unit="mm", dataset="TEST", period=(1992, 2017),
    )  # fmt: skip


def ring(centre, offsets_km, n=1):
    """Points at given distances due north of `centre` (a dot per distance, `n` copies)."""
    return [(centre[0] + d / KM_PER_DEG, centre[1]) for d in offsets_km for _ in range(n)]


# --- which cells are in the circle: the centre rule -----------------------------------------------


def test_a_cell_is_in_the_circle_only_when_its_centre_is_inside():
    centre = (0.0, 100.0)
    # a 55 km wide cell whose centre is 140 km away overlaps a 120 km circle, but its centre is out
    pts = ring(centre, [0, 30, 60, 90, 119, 121, 140, 200])
    cells = cells_at(pts, [fake(0.5, 0.5)] * len(pts))
    inside = cells_inside(cells, *centre, 120.0)
    assert list(inside) == [0, 1, 2, 3, 4]  # 121 and 140 km are outside, even if the cells overlap


def test_a_centre_exactly_on_the_edge_is_inside():
    centre = (0.0, 100.0)
    pts = ring(centre, [0, 20, 40, 60, 80])
    cells = cells_at(pts, [fake(0.5, 0.5)] * len(pts))
    edge = float(haversine_km(centre[0], centre[1], pts[4][0], pts[4][1]))
    assert 4 in cells_inside(cells, *centre, edge)  # distance equal to the radius counts
    assert 4 not in cells_inside(cells, *centre, edge - 1e-6) if edge - 1e-6 >= 75 else True


def test_radius_and_cell_count_limits():
    centre = (0.0, 100.0)
    cells = cells_at(ring(centre, [0, 10, 20, 30, 40, 200]), [fake(0.5, 0.5)] * 6)
    for radius in (74.9, 250.1, 0.0):
        with pytest.raises(SelectionError, match="75 to 250"):
            cells_inside(cells, *centre, radius)
    assert len(cells_inside(cells, *centre, 75.0)) == 5  # exactly 4 or more is enough
    with pytest.raises(SelectionError, match="at least 4"):
        cells_inside(cells_at(ring(centre, [0, 10, 20]), [fake(0.5, 0.5)] * 3), *centre, 100.0)


# --- the family is the circle ------------------------------------------------------------------


def two_clusters():
    """Five cells with a modest trend (each significant alone) far from sixty with none."""
    west = (0.0, 100.0)
    east = (0.0, 110.0)  # about 1,100 km away
    trending = ring(west, [0, 5, 10, 15, 20])
    nulls = ring(east, list(np.arange(0, 90, 1.5)))  # 60 cells within 90 km
    pts = trending + nulls
    summaries = [fake(0.02, 0.02)] * 5 + [fake(0.6, 0.6, slope=0.1)] * 60
    return west, east, cells_at(pts, summaries)


def test_the_same_cells_get_different_verdicts_in_different_circles():
    west, east, cells = two_clusters()
    alone = analyse_circle(cells, *west, 100.0)
    assert alone["cells_inside"] == 5 and alone["counts"]["rise"] == 5
    assert alone["cells"][0]["significance"]["family"]["n_tests"] == 5
    # a correction across the whole box (65 cells) would have made the same five p-values
    # q = 0.02 x 65 / 5 = 0.26: not significant. The circle decides, not the box.
    everything = cells_at(
        list(zip(cells.lat, cells.lon, strict=True)), cells.summaries
    )
    box = [s.ols_p for s in everything.summaries]
    assert stats.false_discovery_control(box, method="bh")[0] == pytest.approx(0.26)


def test_a_circle_with_many_other_cells_corrects_harder():
    # 5 trending and 16 null cells in one circle: a family of 21, so q = 0.02 x 21 / 5 = 0.084
    base = (0.0, 100.0)
    pts = ring(base, [0, 5, 10, 15, 20]) + ring(base, list(np.linspace(25, 100, 16)))
    cells = cells_at(pts, [fake(0.02, 0.02)] * 5 + [fake(0.6, 0.6, slope=0.1)] * 16)
    result = analyse_circle(cells, *base, 120.0)
    assert result["cells_inside"] == 21
    # the same five cells that were all rising in a small circle are now not significant
    assert result["counts"]["rise"] == 0 and result["counts"]["none"] == 21
    assert result["counts"]["unclear"] == 0
    first = result["cells"][0]["significance"]
    assert first["ols_q"] == pytest.approx(0.02 * 21 / 5) and first["verdict"] == "none"


def test_each_cell_is_judged_by_both_tests():
    base = (0.0, 100.0)
    pts = ring(base, [0, 10, 20, 30, 40])
    opposite = replace(fake(0.001, 0.001, slope=-1.0), sen_per_decade=1.0)  # OLS falls, Sen rises
    summaries = [fake(0.001, 0.001), fake(0.001, 0.9), fake(0.9, 0.001), fake(0.9, 0.9), opposite]
    out = analyse_circle(cells_at(pts, summaries), *base, 100.0)
    verdicts = [c["significance"]["verdict"] for c in out["cells"]]
    # OLS only, Mann-Kendall only, neither, both significant but with opposite signs
    assert verdicts == ["rise", "unclear", "unclear", "none", "unclear"]
    fall = [fake(0.001, 0.001, slope=-1.0)] * 4 + [fake(0.9, 0.9)]
    out = analyse_circle(cells_at(pts, fall), *base, 100.0)
    assert out["counts"]["fall"] == 4 and out["counts"]["none"] == 1


def test_cells_keep_their_grid_position_and_the_counts_add_up():
    base = (0.0, 100.0)
    pts = ring(base, [0, 10, 20, 30, 40, 50])
    cells = cells_at(pts, [fake(0.5, 0.5)] * 6)
    cells = OceanCells(**{**cells.__dict__, "k": np.array([7, 9, 12, 14, 30, 31])})
    out = analyse_circle(cells, *base, 100.0)
    assert [c["k"] for c in out["cells"]] == [7, 9, 12, 14, 30, 31]
    assert sum(out["counts"].values()) == out["cells_inside"] == 6
    assert out["expected_by_chance"] == pytest.approx(0.025 * 6)
    json.dumps(out)  # plain JSON: no NaN, no numpy types


def test_a_cell_without_enough_data_is_not_counted_as_a_test():
    base = (0.0, 100.0)
    pts = ring(base, [0, 10, 20, 30, 40, 50])
    short = summarise(np.arange(10.0), "mm", "x")  # under 24 months: no p-values
    cells = cells_at(pts, [short] + [fake(0.001, 0.001)] * 5)
    out = analyse_circle(cells, *base, 100.0)
    assert out["counts"]["no_data"] == 1 and out["counts"]["rise"] == 5
    assert out["cells"][0]["significance"]["family"]["n_tests"] == 5
    assert out["cells"][0]["slope_per_decade"] is None
    json.dumps(out)


# --- the saved per-cell results round-trip -------------------------------------------------------


def test_a_summary_survives_being_saved_and_read_back():
    rng = np.random.default_rng(3)
    t = np.arange(312)
    for series in (0.3 * t / 12 + rng.normal(0, 1, 312), np.arange(10.0)):  # real, then short
        s = summarise(series, "mm", "cell")
        record = json.loads(json.dumps(summary_to_record(s)))  # through real JSON
        back = summary_from_record(record)
        names = ("n_months", "ols_p", "mk_p_ar1", "sen_per_decade", "ols_per_decade", "n_eff", "r1")
        for name in names:
            a, b = getattr(s, name), getattr(back, name)
            assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b), name
        assert back.ols_ci_per_decade[0] == pytest.approx(s.ols_ci_per_decade[0], nan_ok=True)
        assert back.warnings == s.warnings and back.tests_agree == s.tests_agree


def test_missing_file_says_what_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="export_cells.py"):
        load(Path(tmp_path) / "absent.json")


# --- on the real exported cells (skipped when the file is absent) ---------------------------------

REAL = Path(__file__).resolve().parents[2] / "data" / "processed" / "ocean" / "ecco_cell_stats.json"


@pytest.mark.skipif(not REAL.exists(), reason="run scripts/export_cells.py first")
def test_real_cells_are_corrected_across_the_circle_only():
    cells = load(REAL)
    out = analyse_circle(cells, -6.0, 106.9, 150.0)  # the sea off Jakarta
    n = out["cells_inside"]
    assert n >= 4 and out["cells"][0]["significance"]["family"]["n_tests"] == n
    inside = [c["k"] for c in out["cells"]]
    by_k = {int(k): s for k, s in zip(cells.k, cells.summaries, strict=True)}
    p = np.array([by_k[k].ols_p for k in inside])
    q = np.array([c["significance"]["ols_q"] for c in out["cells"]])
    np.testing.assert_allclose(q, stats.false_discovery_control(p, method="bh"), rtol=1e-9)
    # across the whole box the same p-values would be corrected harder
    box_p = np.array([s.ols_p for s in cells.summaries])
    adjusted = stats.false_discovery_control(box_p, method="bh")
    box_q = dict(zip(cells.k.tolist(), adjusted, strict=True))
    harder = [box_q[c["k"]] > c["significance"]["ols_q"] + 1e-12 for c in out["cells"]]
    assert any(harder)
