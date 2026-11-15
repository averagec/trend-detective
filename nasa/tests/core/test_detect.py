"""Tests for the years-needed simulation (core/detect.py). Monotonic checks, not exact values."""

import numpy as np

from trend_detective.core.detect import noise_params, years_needed


def test_bigger_trend_needs_fewer_years():
    small = years_needed(0.2, sigma=0.5, phi=0.3, n_sims=100, seed=1)
    large = years_needed(1.0, sigma=0.5, phi=0.3, n_sims=100, seed=1)
    assert small is not None and large is not None
    assert large <= small


def test_more_noise_needs_more_years():
    quiet = years_needed(0.5, sigma=0.2, phi=0.3, n_sims=100, seed=2)
    noisy = years_needed(0.5, sigma=1.0, phi=0.3, n_sims=100, seed=2)
    assert quiet is not None and noisy is not None
    assert noisy >= quiet


def test_zero_trend_has_no_answer():
    assert years_needed(0.0, sigma=0.5, phi=0.3, n_sims=50) is None


def test_missing_noise_has_no_answer():
    assert years_needed(0.5, sigma=float("nan"), phi=0.3, n_sims=50) is None


def test_unreachable_trend_returns_none():
    # Enormous noise, tiny trend: even 100 years will not reach 90%.
    assert years_needed(0.001, sigma=50.0, phi=0.9, n_sims=50, max_years=20) is None


def test_noise_params_of_a_known_series():
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 2.0, 2400)  # deseasonalising removes nothing from white noise of this size
    sigma, phi = noise_params(x, steps_per_year=12)
    assert 1.8 < sigma < 2.2
    assert abs(phi) < 0.1
