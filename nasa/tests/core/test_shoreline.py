"""Golden tests for core/shoreline.py: synthetic coasts with known answers."""
import numpy as np
import pytest

from trend_detective.core.shoreline import (
    analyze_shoreline,
    month_index,
    monthly_series,
    otsu_threshold,
    shoreline_position_m,
    water_mask,
)


def coast(boundary_px: int, rows=20, width=100) -> np.ndarray:
    """Water (True) east of boundary_px, land west of it."""
    m = np.zeros((rows, width), dtype=bool)
    m[:, boundary_px:] = True
    return m


def test_otsu_separates_bimodal_db():
    rng = np.random.default_rng(0)
    db = np.concatenate([rng.normal(-22, 1.5, 5000), rng.normal(-8, 2, 5000)])
    t = otsu_threshold(db)
    assert -20 < t < -10
    wm = water_mask(db, t)
    assert wm[:5000].mean() > 0.95 and wm[5000:].mean() < 0.05


@pytest.mark.parametrize("side", ["east", "west", "north", "south"])
def test_position_same_for_all_sea_sides(side):
    m = coast(60)
    rot = {"east": m, "west": m[:, ::-1], "north": np.rot90(m, 1), "south": np.rot90(m, -1)}[side]
    assert shoreline_position_m(rot, pixel_m=10, sea_side=side) == 600.0


def test_ignores_small_land_specks():
    m = coast(60)
    m[5, 80] = False  # a boat/speckle in the sea
    assert shoreline_position_m(m, 10) == 600.0


def test_gap_limit():
    with pytest.raises(ValueError):
        monthly_series(np.array([0, 1, 5]), np.array([1.0, 2.0, 3.0]))
    s, first = monthly_series(np.array([0, 1, 3]), np.array([1.0, 2.0, 4.0]))
    assert first == 0 and s.tolist() == [1.0, 2.0, 3.0, 4.0]


def test_recovers_known_seaward_trend():
    # 0.5 px/yr at 10 m pixels = 5 m/yr = +50 m/decade, 12 years, monthly scenes
    months = np.arange(144)
    vals = [shoreline_position_m(coast(int(round(30 + 0.5 * mo / 12))), 10) for mo in months]
    # per-month boundary is rounded to whole pixels, so allow rounding noise
    res = analyze_shoreline(monthly_series(months + month_index(2012, 1), np.array(vals))[0])
    assert res.m_per_decade == pytest.approx(50.0, abs=4.0)
    assert res.ols.p_value < 0.05 and res.mk.p_value < 0.05
    assert not res.warnings


def test_flat_noisy_coast_not_significant_and_short_record_warns():
    rng = np.random.default_rng(1)
    series = 600 + rng.normal(0, 5, 60)
    res = analyze_shoreline(series)
    assert res.ols.p_value > 0.05
    assert res.warnings
