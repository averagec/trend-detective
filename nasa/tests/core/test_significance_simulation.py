"""Seeded simulations for the significance engine. The acceptance ranges are written in
docs/decisions/0009-significance-engine-both-tests-after-correction.md before these ran, and are
never loosened to make a change pass.

Families of 50 series, 10 years of monthly data, 100 runs per scenario. Under a global null
Benjamini-Hochberg holds the chance of any flagged series near 5% (lower with two tests required);
12 of 100 is the 99th percentile of Binomial(100, 0.05) rounded up. Measured values are in the ADR.
"""

import numpy as np
from scipy.signal import lfilter

from trend_detective.core.significance import Item, assess_family
from trend_detective.core.summary import summarise

RUNS, N_SERIES, N = 100, 50, 120  # runs, series per family, months per series


def ar1(rng, phi):
    burn = 60
    e = rng.normal(0, 1, N + burn)
    return lfilter([1.0], [1.0, -phi], e)[burn:]


def judge(series):
    items = [Item(summarise(y, "K", "s"), "s", "K") for y in series]
    return items, assess_family(items, "circle")


def simulate(make_family, seed):
    """Run the scenario and return the share of runs with any flagged series, with a mixed signal
    (a rise and a fall together), and with an uncorrected mixed signal (p < 0.05 per series)."""
    rng = np.random.default_rng(seed)
    any_flag = mixed = raw_mixed = 0
    flagged_truth = []
    for _ in range(RUNS):
        items, out = judge(make_family(rng))
        verdicts = [a.verdict for a in out]
        any_flag += any(a.significant for a in out)
        mixed += "rise" in verdicts and "fall" in verdicts
        raw_up = any(i.summary.ols_significant and i.summary.ols_per_decade > 0 for i in items)
        raw_down = any(i.summary.ols_significant and i.summary.ols_per_decade < 0 for i in items)
        raw_mixed += raw_up and raw_down
        flagged_truth.append(verdicts)
    return {
        "any": any_flag / RUNS,
        "mixed": mixed / RUNS,
        "raw_mixed": raw_mixed / RUNS,
        "verdicts": flagged_truth,
    }


def test_a_independent_null_series_are_rarely_flagged():
    r = simulate(lambda rng: [rng.normal(0, 1, N) for _ in range(N_SERIES)], seed=101)
    assert r["any"] <= 0.12
    assert r["mixed"] <= 0.12
    # the problem being fixed: without correction about half of null 50-series sets look "mixed"
    assert r["raw_mixed"] >= 0.35


def test_b_neighbouring_cells_sharing_noise_are_rarely_flagged():
    def family(rng):
        common = rng.normal(0, 1, N)  # shared by every cell: correlation 0.5 between cells
        return [common + rng.normal(0, 1, N) for _ in range(N_SERIES)]

    assert simulate(family, seed=102)["any"] <= 0.12


def test_c_autocorrelated_null_series_are_rarely_flagged():
    r = simulate(lambda rng: [ar1(rng, 0.6) for _ in range(N_SERIES)], seed=103)
    assert r["any"] <= 0.15


def test_d_real_trends_among_nulls_are_found_and_the_nulls_are_not():
    slopes = [0.02, 0.02, -0.02]  # per month: about 2.4 noise standard deviations per decade

    def family(rng):
        t = np.arange(N)
        real = [s * t + rng.normal(0, 1, N) for s in slopes]
        return real + [rng.normal(0, 1, N) for _ in range(N_SERIES - len(slopes))]

    r = simulate(family, seed=104)
    found = [v[:3] == ["rise", "rise", "fall"] for v in r["verdicts"]]
    assert np.mean(found) >= 0.95
    # Benjamini-Hochberg promises a low share of false flags AMONG the flagged series (the false
    # discovery proportion), not a low chance of any false flag. ADR 0009 explains the amendment.
    fdp = []
    for v in r["verdicts"]:
        flagged = [x in ("rise", "fall") for x in v]
        fdp.append(sum(flagged[3:]) / sum(flagged) if sum(flagged) else 0.0)
    assert np.mean(fdp) <= 0.08
