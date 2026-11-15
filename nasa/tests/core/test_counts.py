"""Golden tests for the count trend (core/counts.py)."""

import numpy as np
import pytest

from trend_detective.core.counts import count_trend


def test_steady_rise_of_one_event_per_year_is_ten_per_decade():
    counts = np.arange(1, 40, dtype=float)  # 1, 2, ..., 39 events
    res = count_trend(counts)
    assert res.sen_per_decade == pytest.approx(10.0)
    assert res.significant
    assert res.direction == "rise"


def test_constant_counts_have_no_trend():
    res = count_trend(np.full(30, 3.0))
    assert res.sen_per_decade == pytest.approx(0.0)
    assert res.mk_p == pytest.approx(1.0)
    assert res.direction == "none"


def test_falling_counts_are_a_fall():
    res = count_trend(np.arange(39, 0, -1, dtype=float))
    assert res.direction == "fall"
    assert res.sen_per_decade < 0


def test_mostly_zero_years_get_a_warning():
    counts = np.zeros(39)
    counts[-3:] = 2
    res = count_trend(counts)
    assert res.zero_share > 0.5
    assert any("no events" in w for w in res.warnings)


def test_too_few_years_is_refused():
    with pytest.raises(ValueError):
        count_trend(np.array([1.0, 2.0]))
