"""Golden tests for the significance engine (docs/decisions/0009): the ladder, the corrections, the
wording. Summaries are built by hand where the answer is worked out on paper, and with the real
`summarise` where the point is that the pieces fit together."""

import numpy as np
import pytest

from trend_detective.core.significance import (
    Item,
    assess_family,
    assess_single,
    verdict_for,
    warning_code,
)
from trend_detective.core.summary import Summary, summarise


def fake(ols_p, mk_p, slope=0.2, sen=None, warnings=()):
    """A summary with chosen p-values and slopes (per decade); everything else is filler."""
    sen = slope if sen is None else sen
    return Summary(
        n_months=240,
        n_years=20.0,
        ols_per_decade=slope,
        ols_ci_per_decade=(slope - 0.1, slope + 0.1),
        ols_p=ols_p,
        ols_significant=ols_p < 0.05,
        sen_per_decade=sen,
        mk_p=mk_p,
        mk_significant=mk_p < 0.05,
        tests_agree=True,
        warnings=tuple(warnings),
        sentence="(summary sentence)",
        mk_p_ar1=mk_p,
        mk_ar1_significant=mk_p < 0.05,
    )


def item(s, label="Air temperature", unit="K"):
    return Item(s, label, unit)


# --- the ladder -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ols_q", "mk_q", "ols_slope", "sen_slope", "expected"),
    [
        (0.01, 0.01, +0.2, +0.18, "rise"),
        (0.01, 0.01, -0.2, -0.18, "fall"),
        (0.01, 0.01, +0.2, -0.18, "unclear"),  # both significant, opposite signs
        (0.01, 0.01, -0.2, +0.18, "unclear"),
        (0.01, 0.20, +0.2, +0.20, "unclear"),  # only OLS
        (0.20, 0.01, +0.2, +0.20, "unclear"),  # only Mann-Kendall
        (0.20, 0.30, +0.2, +0.20, "none"),
        (0.05, 0.01, +0.2, +0.20, "unclear"),  # alpha itself is not significant: strictly below
        (0.049999, 0.049999, +0.2, +0.2, "rise"),
        (0.01, 0.01, 0.0, 0.0, "unclear"),  # no slope cannot be a rise or a fall
        (np.nan, 0.01, +0.2, +0.2, "no_data"),
        (0.01, np.nan, +0.2, +0.2, "no_data"),
        (np.nan, np.nan, np.nan, np.nan, "no_data"),
    ],
)
def test_the_ladder(ols_q, mk_q, ols_slope, sen_slope, expected):
    assert verdict_for(ols_q, mk_q, ols_slope, sen_slope) == expected


# --- correction: one family, worked by hand ---------------------------------------------------


def test_a_family_is_corrected_separately_for_each_test():
    # OLS p-values .01 .04 .03 .005 -> sorted .005 .01 .03 .04, times 4/rank: .02 .02 .04 .04,
    # so the adjusted values in the original order are .02 .04 .04 .02 (the textbook example).
    # Mann-Kendall p-values .001 .2 .04 .5 -> sorted .001 .04 .2 .5, times 4/rank:
    # .004 .08 .2667 .5, so in the original order .004 .2667 .08 .5.
    ols = [0.01, 0.04, 0.03, 0.005]
    mk = [0.001, 0.2, 0.04, 0.5]
    out = assess_family([item(fake(a, b)) for a, b in zip(ols, mk, strict=True)], "layer")
    np.testing.assert_allclose([a.ols_q for a in out], [0.02, 0.04, 0.04, 0.02], rtol=1e-12)
    np.testing.assert_allclose([a.mk_q for a in out], [0.004, 0.8 / 3, 0.08, 0.5], rtol=1e-12)
    assert [a.verdict for a in out] == ["rise", "unclear", "unclear", "unclear"]
    assert {a.n_tests for a in out} == {4} and {a.family for a in out} == {"layer"}
    assert out[0].expected_by_chance == pytest.approx(0.1)  # 4 tests x 2.5% per direction


def test_a_trend_significant_alone_but_not_after_correction_is_not_called_significant():
    # The case that used to contradict itself on screen: significant alone, not in its family.
    # OLS p .041, .030, .5 -> sorted .03 (1), .041 (2), .5 (3), times 3/rank: .09, .0615, .5, and
    # the running minimum from the top makes .041 and .030 both .0615: above 0.05 after correction.
    family = [fake(0.041, 0.005), fake(0.030, 0.2), fake(0.5, 0.6)]
    label = "Mean 2 m air temperature in Eastern China"
    out = assess_family([item(s, label) for s in family], "layer")
    assert out[0].ols_p < 0.05 < out[0].ols_q
    assert out[0].verdict != "rise" and not out[0].significant
    assert "no significant trend detected (yet)" in out[0].sentence
    assert "statistically significant" not in out[0].sentence


def test_a_single_series_uses_the_plain_p_values():
    a = assess_single(fake(0.03, 0.01), "Rain", "mm day-1")
    assert (a.family, a.n_tests, a.expected_by_chance) == ("none", None, None)
    assert a.ols_q == a.ols_p == 0.03 and a.mk_q == a.mk_p_ar1 == 0.01
    assert a.verdict == "rise"
    with pytest.raises(ValueError):
        assess_family([item(fake(0.1, 0.1)), item(fake(0.2, 0.2))], "none")
    with pytest.raises(ValueError):
        assess_family([item(fake(0.1, 0.1))], "everything")


def test_series_without_a_p_value_are_not_counted_and_do_not_change_the_others():
    short = summarise(np.arange(10.0), "K", "x")  # under 24 months: every statistic is missing
    rest = [fake(0.01, 0.01), fake(0.04, 0.04), fake(0.3, 0.3)]
    with_short = assess_family([item(short), *[item(s) for s in rest]], "layer")
    without = assess_family([item(s) for s in rest], "layer")
    assert with_short[0].verdict == "no_data" and not with_short[0].significant
    assert np.isnan(with_short[0].ols_q)
    assert with_short[0].n_tests == without[0].n_tests == 3
    np.testing.assert_allclose([a.ols_q for a in with_short[1:]], [a.ols_q for a in without])
    assert "not enough data" in with_short[0].sentence


def test_the_order_of_the_family_does_not_matter():
    rng = np.random.default_rng(4)
    ps = rng.uniform(0, 0.2, (12, 2))
    items = [item(fake(a, b, slope=1.0 if a < 0.1 else -1.0)) for a, b in ps]
    base = assess_family(items, "circle")
    order = rng.permutation(12)
    shuffled = assess_family([items[i] for i in order], "circle")
    for pos, original in enumerate(order):
        assert shuffled[pos].verdict == base[original].verdict
        assert shuffled[pos].ols_q == pytest.approx(base[original].ols_q)


def test_invariants_over_random_families():
    rng = np.random.default_rng(9)
    for _ in range(50):
        n = int(rng.integers(2, 40))
        sign = rng.choice([-1.0, 1.0], n)
        items = []
        for s in sign:
            p1, p2 = rng.uniform(0, 1) ** 2, rng.uniform(0, 1) ** 2
            items.append(item(fake(p1, p2, slope=s, sen=s * rng.choice([1, 1, -1]))))
        for a, it in zip(assess_family(items, "layer"), items, strict=True):
            assert a.ols_q >= a.ols_p - 1e-15 and a.mk_q >= a.mk_p_ar1 - 1e-15 and a.ols_q <= 1.0
            if a.significant:  # a rise or fall always has both q below 0.05 and agreeing slopes
                assert a.ols_q < 0.05 and a.mk_q < 0.05
                assert np.sign(it.summary.ols_per_decade) == np.sign(it.summary.sen_per_decade)
                assert a.verdict == ("rise" if it.summary.ols_per_decade > 0 else "fall")
            assert a.significant == (a.verdict in ("rise", "fall"))


# --- wording (science rule 7) -------------------------------------------------------------------


def test_the_sentence_uses_only_the_two_allowed_phrases():
    family = [
        fake(0.001, 0.001, 0.3),
        fake(0.001, 0.001, -0.3),
        fake(0.01, 0.6, 0.1),
        fake(0.7, 0.8),
    ]
    for a in assess_family([item(s, "Rain in X", "mm day-1") for s in family], "layer"):
        sig = "statistically significant at 95%" in a.sentence
        none = "no significant trend detected (yet)" in a.sentence
        assert sig != none  # exactly one of the two
        assert sig == a.significant
        assert not any(w in a.sentence.lower() for w in ("prove", "caused", "because of"))
        assert "mm day-1 per decade" in a.sentence


def test_a_clear_single_trend_reads_exactly_as_before():
    rng = np.random.default_rng(0)
    t = np.arange(240)
    y = 280 + 3 * np.sin(t * 2 * np.pi / 12) + 0.003 * t + rng.normal(0, 0.4, 240)
    s = summarise(y, "K", "Demo")
    a = assess_single(s, "Demo", "K")
    assert a.verdict == "rise"
    assert a.sentence == s.sentence  # same words and numbers as the per-series summary


def test_correction_is_named_only_when_there_is_a_family_of_more_than_one():
    strong = [fake(1e-6, 1e-6, 0.3) for _ in range(3)]
    in_family = assess_family([item(s) for s in strong], "layer")[0].sentence
    assert in_family.endswith("significant at 95% after correcting for 3 tests at once.")
    assert "correcting" not in assess_family([item(strong[0])], "layer")[0].sentence
    assert "correcting" not in assess_single(strong[0], "Air temperature", "K").sentence


# --- warnings -----------------------------------------------------------------------------------


def test_warnings_carry_codes_and_the_ladder_adds_its_own():
    stale = "The two tests disagree: check for outliers or a non-linear pattern before trusting it."
    short = "Only 5.0 years of data; trends under 10 years are not reliable."
    s = fake(1e-6, 0.4, warnings=(short, stale))
    a = assess_single(s, "x", "K")
    codes = dict(a.warnings)
    assert a.verdict == "unclear"
    assert "short_record" in codes and "one_test_significant" in codes
    assert not any(text == stale for _, text in a.warnings)  # the uncorrected note is replaced
    both = assess_single(fake(1e-6, 1e-6, slope=0.2, sen=-0.2), "x", "K")
    assert [c for c, _ in both.warnings] == ["tests_disagree"]
    assert warning_code("12% of months are missing.") == "missing_months"
    assert warning_code("x: not enough data for a trend") == "not_enough_data"


# --- the pieces fit together on real series ------------------------------------------------------


def test_a_family_of_real_series_gives_rise_fall_and_none():
    rng = np.random.default_rng(1)
    t = np.arange(240)

    def series(slope):
        return 280 + 3 * np.sin(t * 2 * np.pi / 12) + slope * t + rng.normal(0, 0.5, 240)

    items = [
        item(summarise(series(0.01), "K", "up"), "up"),
        item(summarise(series(-0.01), "K", "down"), "down"),
        item(summarise(series(0.0), "K", "flat"), "flat"),
    ]
    assert [a.verdict for a in assess_family(items, "layer")] == ["rise", "fall", "none"]


# --- explanation: why the verdict, in plain words ----------------------------------------------


def test_each_verdict_has_an_explanation_that_names_the_tests_and_the_slopes():
    s = fake(0.01, 0.01, slope=0.2, sen=0.18)
    rise = assess_single(s, "x", "K").explanation
    assert rise == (
        "Both tests are below 0.05, and their slopes have the same sign: "
        "OLS +0.20 and Sen +0.18 K per decade."
    )
    pair = [item(fake(0.01, 0.01, slope=0.2, sen=0.18)), item(fake(0.9, 0.9))]
    family = assess_family(pair, "layer")
    assert family[0].explanation.startswith(
        "Both tests are below 0.05 after correcting for 2 tests at once"
    )
    opposite = assess_single(fake(0.01, 0.01, slope=0.2, sen=-0.18), "x", "K").explanation
    assert "opposite signs" in opposite and "not clear" in opposite
    only_ols = assess_single(fake(0.01, 0.20, slope=0.2, sen=0.2), "x", "K").explanation
    assert only_ols == (
        "Only the OLS test is below 0.05 (OLS p 0.010; Mann-Kendall p 0.200). "
        "The two tests do not agree."
    )
    only_mk = assess_single(fake(0.20, 0.01, slope=0.2, sen=0.2), "x", "K").explanation
    assert only_mk.startswith(
        "Only the Mann-Kendall test is below 0.05 (Mann-Kendall p 0.010; OLS p 0.200)"
    )
    none = assess_single(fake(0.30, 0.40), "x", "K").explanation
    assert none == "Neither test is below 0.05 (OLS p 0.300; Mann-Kendall p 0.400)."


def test_explanation_reads_q_values_and_small_values_are_written_as_below_0_001():
    strong = [fake(1e-6, 1e-6, slope=0.3, sen=0.3), fake(0.9, 0.9)]
    out = assess_family([item(s) for s in strong], "layer")
    assert out[0].verdict == "rise"
    assert out[0].explanation == (
        "Both tests are below 0.05 after correcting for 2 tests at once, and their slopes have the "
        "same sign: OLS +0.30 and Sen +0.30 K per decade."
    )
    lone = assess_family([item(fake(1e-6, 0.9)), item(fake(0.9, 0.9))], "layer")[0]
    assert lone.verdict == "unclear"
    assert lone.explanation == (
        "Only the OLS test is below 0.05 after correcting for 2 tests at once "
        "(OLS q < 0.001; Mann-Kendall q 0.900). The two tests do not agree."
    )


def test_explanation_with_a_missing_p_value_says_there_is_too_little_data():
    out = assess_single(fake(np.nan, 0.01), "x", "K")
    assert out.verdict == "no_data"
    assert out.explanation == "Too few valid values to run both tests."


def test_explanation_avoids_the_forbidden_words():
    rng = np.random.default_rng(2)
    t = np.arange(240)
    items = []
    for k in (-1, 0, 1):
        y = 280 + 3 * np.sin(t * np.pi / 6) + k * 0.01 * t + rng.normal(0, 0.5, 240)
        items.append(item(summarise(y, "K", f"s{k}"), f"s{k}"))
    for a in assess_family(items, "layer"):
        assert not any(w in a.explanation.lower() for w in ("prove", "caused", "because of"))
