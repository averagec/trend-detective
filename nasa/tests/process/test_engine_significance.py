"""The trend engine hands its series to core/significance.py (ADR 0009): map regions, circle cells
and a city are judged by both tests after correction. Synthetic data, offline."""

import math

import numpy as np
from scipy.signal import lfilter

from trend_detective.process.regional_map import build_map
from trend_detective.process.selection import Grid, analyse_circle, analyse_city

GRID = Grid(lat=-12.0 + 0.5 * np.arange(39), lon=94.375 + 0.625 * np.arange(77))
JAKARTA = (-6.1805357, 106.8280366)


def write_csv(root, series):
    """series: {region: values (months from 1990-01)}, all variable t2m in K."""
    lines = ["region,variable,period,value,unit,n_cells,n_valid,n_days"]
    for region, values in series.items():
        for i, v in enumerate(values):
            p = f"{1990 + i // 12}-{i % 12 + 1:02d}"
            lines.append(f"{region},t2m,{p},{'' if v is None else repr(float(v))},K,10,10,")
    path = root / "merra2" / "monthly_regional.csv"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def regions_of(root, **kwargs):
    """The map's regions for the years of the synthetic data (stated, so the test does not depend
    on the project window, which limits any map to 1980-2018)."""
    payload = build_map(root, "merra2:t2m", first=1990, last=2009, **kwargs)
    return {r["key"]: r for r in payload["regions"]}


def noisy(slope, seed, n=240):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return 280 + 3 * np.sin(2 * np.pi * t / 12) + slope * t + rng.normal(0, 0.5, n)


def remembering(slope, seed, phi=0.6, n=240):
    """A trend on strongly autocorrelated noise: the unadjusted Mann-Kendall is over-confident."""
    rng = np.random.default_rng(seed)
    noise = lfilter([1.0], [1.0, -phi], rng.normal(0, 0.5, n + 60))[60:]
    t = np.arange(n)
    return 280 + 3 * np.sin(2 * np.pi * t / 12) + slope * t + noise


def test_map_direction_needs_both_tests_after_correction(tmp_path):
    # se_asia_maritime (phi 0.6, seed 189): OLS p 0.039 (it already allows for memory), unadjusted
    # Mann-Kendall p 0.0006, adjusted Mann-Kendall p 0.087. The old rule (OLS and the unadjusted
    # Mann-Kendall, each corrected) called this a rise; with the adjusted test it is "unclear".
    write_csv(
        tmp_path,
        {"east_asia_land": noisy(0.0025, 1), "se_asia_maritime": remembering(0.0012, 189)},
    )
    regions = regions_of(tmp_path)
    east, se = regions["east_asia_land"], regions["se_asia_maritime"]
    assert east["direction"] == "rise" and east["significance"]["verdict"] == "rise"
    assert se["ols_p_adj"] < 0.05 and se["mk_p_adj"] < 0.05, "the old rule would have said rise"
    assert se["mk_p_ar1_adj"] >= 0.05
    assert se["direction"] == "unclear" and se["significance"]["verdict"] == "unclear"
    assert [w["code"] for w in se["significance"]["warnings"]] == ["one_test_significant"]
    assert "no significant trend detected (yet)" in se["significance"]["sentence"]


def test_map_blocks_describe_the_layer_family_and_skip_regions_without_data(tmp_path):
    values = {
        "east_asia_land": noisy(0.003, 2),
        "north_asia_siberia": noisy(0.0, 3),
        "se_asia_maritime": [None] * 240,  # a box with no valid values
    }
    write_csv(tmp_path, values)
    payload = build_map(tmp_path, "merra2:t2m", first=1990, last=2009)
    regions = {r["key"]: r for r in payload["regions"]}
    assert regions["se_asia_maritime"]["status"] == "no_data"
    assert "significance" not in regions["se_asia_maritime"]
    for key in ("east_asia_land", "north_asia_siberia"):
        fam = regions[key]["significance"]["family"]
        assert (fam["name"], fam["n_tests"]) == ("layer", 2)  # the empty region is not a test
        assert "_summary" not in regions[key] and "_label" not in regions[key]
    assert "both" in payload["adjustment"] and "agree in sign" in payload["adjustment"]
    east = regions["east_asia_land"]
    assert east["ols_p_adj"] == east["significance"]["ols_q"]


def test_yearly_map_gets_the_same_block(tmp_path):
    write_csv(tmp_path, {"east_asia_land": noisy(0.003, 2), "north_asia_siberia": noisy(0.0, 3)})
    regions = regions_of(tmp_path, freq="yearly")
    assert regions["east_asia_land"]["significance"]["verdict"] == "rise"
    assert regions["north_asia_siberia"]["direction"] == "none"


def circle_cube():
    rng = np.random.default_rng(11)
    n = 12 * 24
    t = np.arange(n, dtype=float)[:, None, None]
    slope = np.zeros((39, 77))
    slope[10:13, 18:22] = 0.004
    slope[13:16, 18:22] = -0.004
    season = 3 * np.sin(2 * np.pi * t / 12)
    return 290.0 + slope[None] * t + season + rng.normal(0, 0.4, (n, 39, 77))


def periods():
    return [f"{1990 + i // 12:04d}{i % 12 + 1:02d}" for i in range(12 * 24)]


def test_circle_cells_are_rising_or_falling_by_the_ladder():
    circle = analyse_circle(circle_cube(), periods(), GRID, *JAKARTA, 150.0, "K", "T2M")
    verdicts = [c.assessment.verdict for c in circle.cells]
    assert circle.rising == verdicts.count("rise") and circle.falling == verdicts.count("fall")
    assert circle.rising + circle.falling + circle.not_significant == circle.cells_used
    for c in circle.cells:
        a = c.assessment
        assert c.p_adj == a.ols_q  # the same Benjamini-Hochberg numbers as before
        assert a.family == "circle" and a.n_tests == circle.cells_used
        assert c.significant == a.significant
        if c.rising or c.falling:
            assert a.ols_q < 0.05 and a.mk_q < 0.05
    assert circle.average_assessment.family == "none"  # the area average is a reference, alone


def test_a_city_is_judged_on_its_own():
    city = analyse_city(circle_cube(), periods(), GRID, *JAKARTA, "K", "T2M, Jakarta", "Jakarta")
    a = city.assessment
    assert (a.family, a.n_tests) == ("none", None)
    assert a.ols_q == a.ols_p and a.mk_q == a.mk_p_ar1
    assert a.verdict in ("rise", "fall", "none", "unclear")
    if a.verdict == "rise":
        assert a.sentence == city.summary.sentence  # a clear trend reads as it always did
    assert not math.isnan(a.ols_p)


def test_years_before_a_dataset_begins_are_padding_not_missing_months(tmp_path):
    # GRACE starts in 2002, GPCP in 1983: the timeline opens with the project window (1980), but the
    # steps before the data are padding. They must not be reported as "65% of months are missing".
    write_csv(tmp_path, {"east_asia_land": noisy(0.002, 5, n=240)})  # data: 1990-01 to 2009-12
    for freq in ("monthly", "yearly"):
        region = build_map(tmp_path, "merra2:t2m", freq=freq)["regions"][0]  # the whole window
        assert region["first_period"] in ("1980-01", "1980")  # the timeline (their design)
        assert region["missing_share"] == 0
        assert not any(w["code"] == "missing_months" for w in region["warnings"])
        assert not any(w["code"] == "missing_months" for w in region["significance"]["warnings"])
    monthly = build_map(tmp_path, "merra2:t2m")["regions"][0]
    assert monthly["n_points"] == 240 and monthly["last_period"] == "2009-12"
    # a real gap inside the data is still reported
    gappy = noisy(0.002, 5, n=240)
    gappy = [None if 40 <= i < 80 else v for i, v in enumerate(gappy)]
    write_csv(tmp_path / "gappy", {"east_asia_land": gappy})
    region = build_map(tmp_path / "gappy", "merra2:t2m")["regions"][0]
    assert any(w["code"] == "missing_months" for w in region["warnings"])
