"""The sentence that compares the monthly and the yearly view (process/analyse_trends._comparison).

Which view has more power depends on how alike neighbouring months are, so the sentence compares the
effective number of independent values, and never claims more power for a view that did not find
the trend (found by a dry run on Ambon sea level)."""

from types import SimpleNamespace

from trend_detective.process.analyse_trends import _comparison


def view(verdict, n_months, n_eff, slope=0.26):
    return SimpleNamespace(
        assessment=SimpleNamespace(verdict=verdict),
        summary=SimpleNamespace(n_months=n_months, n_eff=n_eff, ols_per_decade=slope),
    )


def test_agreeing_views_say_so():
    assert _comparison(view("rise", 300, 40), view("rise", 25, 20), "mm") == (
        "The monthly and the yearly view agree: a rise."
    )


def test_too_few_years_for_a_yearly_view():
    assert "too few full years" in _comparison(view("rise", 300, 40), view("no_data", 2, 2), "mm")


def test_monthly_finds_it_and_has_clearly_more_independent_values():
    t = _comparison(view("rise", 468, 156), view("none", 39, 28), "mm/day")
    assert "the monthly view has more power" in t
    assert "about 156 independent values, against about 28" in t
    assert t.endswith("the two views differ in significance, not in the trend.")


def test_yearly_finds_it_and_has_clearly_more_independent_values():
    t = _comparison(view("none", 312, 6), view("rise", 26, 12), "mm")
    assert "the yearly view has more power" in t


def test_similar_information_says_the_result_sits_near_the_limit():
    """Ambon: 312 months count as 9 independent values, 26 yearly as 10; yearly finds a rise."""
    t = _comparison(view("none", 312, 9.0), view("rise", 26, 9.6), "mm")
    assert "about the same information" in t and "close to the 5% limit" in t
    assert "less power" not in t


def test_the_view_that_found_it_has_fewer_independent_values_so_no_power_claim_for_the_other():
    """Kupang: monthly 10 independent values, yearly 8; the yearly view finds a rise."""
    t = _comparison(view("unclear", 312, 10.0), view("rise", 26, 8.0), "mm")
    assert "the monthly view has more independent values, but the result sits close" in t
    assert "tips differently in each view" in t
    assert "more power" not in t


def test_neither_view_finds_a_trend_but_the_verdicts_differ():
    t = _comparison(view("none", 300, 20), view("unclear", 25, 18), "mm")
    assert "about the same information" in t


def test_missing_counts_fall_back_to_a_plain_statement():
    t = _comparison(view("rise", 300, float("nan")), view("none", 25, 9), "mm")
    assert "differ in significance, not in the trend" in t and "independent" not in t
