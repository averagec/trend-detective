"""Golden tests for Benjamini-Hochberg. Worked by hand."""

import numpy as np

from trend_detective.core.trend import benjamini_hochberg


def test_hand_worked_example():
    # sorted p: 0.01, 0.03, 0.04 (m = 3). Scaled: 0.03, 0.045, 0.04. Running minimum from the top:
    # 0.03, 0.04, 0.04. Back in input order: 0.01 -> 0.03, 0.04 -> 0.04, 0.03 -> 0.04.
    adj = benjamini_hochberg([0.01, 0.04, 0.03])
    assert np.allclose(adj, [0.03, 0.04, 0.04])


def test_nan_is_not_counted_as_a_test():
    # m = 2: 0.01 * 2 / 1 = 0.02, 0.03 * 2 / 2 = 0.03.
    adj = benjamini_hochberg([0.01, np.nan, 0.03])
    assert np.isnan(adj[1])
    assert np.allclose(adj[[0, 2]], [0.02, 0.03])


def test_adjusted_values_never_exceed_one():
    adj = benjamini_hochberg([0.9, 0.95])
    assert np.all(adj <= 1.0)
