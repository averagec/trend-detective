"""The noise lineup and the case verdict. Pure functions: no I/O, no network.

Owns: the question "could random noise with the same wobble have made this trend?" and the
robustness checks a case must survive before it is called detected. It never computes a trend
itself: every slope and p-value comes from `core.summary.summarise` and `core.trend`; the verdict
ladder (both tests, same sign) comes from `core.significance.assess_single`.

The lineup: build `n_sims` records with the same lag-1 autocorrelation and the same residual
spread as the real one, and NO trend (AR(1) noise, seeded so the same record always gets the same
answer). Count how many fakes have a slope as strong as the real one. Fewer than 5% is the third
piece of evidence, next to the two tests.

Case verdict (three labels, the game's words):
  "detected"      the engine says rise or fall, the lineup agrees, and every check below passes
  "suspect"       significant evidence, but a check fails (or a known instrument change is inside
                  the window and a test is significant): not safe to trust as it stands
  "not_detected"  not enough evidence yet (includes records under 10 years)
Two views of one record: "monthly" (the months, seasonal cycle removed) and "yearly" (the yearly
averages of those seasonal anomalies, analysed with steps of one year). Same engine, same checks,
same verdict words; the yearly view has fewer points and so less power (ADR 0011).
Rules: docs/science-rules.md, docs/decisions/0010-case-verdict-on-the-engine.md.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np
from scipy.signal import lfilter

from trend_detective.core.detect import noise_params, years_needed
from trend_detective.core.significance import ALPHA, Assessment, assess_single
from trend_detective.core.summary import MIN_YEARS, MONTHS_PER_DECADE, Summary, summarise
from trend_detective.core.trend import deseasonalize, ols_trend

N_SIMS = 1000
LATER_STARTS = (3, 5, 8)  # years cut from the front, each only if 10 years remain
LATER_START_P = 0.1  # the later window must still point the same way, Mann-Kendall p below this
MAX_CHANGE = 0.35  # dropping one year may move the slope by at most this share
BORDERLINE_P = 0.15  # a test p-value below this (but not below 0.05) is "close": our choice
VERDICTS = ("detected", "suspect", "not_detected")
FREQUENCIES = ("monthly", "yearly")
MIN_MONTHS_PER_YEAR = 10  # a yearly average needs this many of the 12 months


@dataclass(frozen=True)
class Check:
    code: str  # stable machine name
    text: str  # plain words, with the numbers that decided it
    ok: bool


@dataclass(frozen=True)
class Lineup:
    n_sims: int
    beat: int  # fakes whose slope is as strong as the real one (either direction)
    share: float  # beat / n_sims
    observed_per_decade: float  # the real OLS slope, units per decade
    sims_per_decade: np.ndarray  # the fakes' slopes, units per decade, for drawing the histogram


@dataclass(frozen=True)
class CaseResult:
    verdict: str  # one of VERDICTS
    summary: Summary
    assessment: Assessment  # the engine's ladder for this series alone (family "none")
    lineup: Lineup | None  # None when there is too little data to simulate
    checks: tuple[Check, ...]
    years: float  # years with data
    years_needed: float | None  # for a not_detected case: record length that would detect it
    explanation: str
    frequency: str = "monthly"
    analysed: np.ndarray | None = None  # what the tests ran on: monthly anomalies or yearly means
    headline: str = ""  # one plain-language sentence: what was found and why


def annual_means(anomalies: np.ndarray, min_months: int = MIN_MONTHS_PER_YEAR) -> np.ndarray:
    """Yearly averages of monthly anomalies (January first). A year with fewer than `min_months`
    months with a value is NaN, so a partly missing year is not averaged over the wrong season."""
    a = np.asarray(anomalies, dtype=float)
    years = -(-a.size // 12)
    padded = np.full(years * 12, np.nan)
    padded[: a.size] = a
    m = padded.reshape(years, 12)
    count = np.isfinite(m).sum(axis=1)
    mean = np.nansum(m, axis=1) / np.maximum(count, 1)
    return np.where(count >= min_months, mean, np.nan)


def _seed(values: np.ndarray, extra: str) -> int:
    """A seed from the data itself: the same record always gets the same lineup."""
    raw = np.nan_to_num(values, nan=-9999.0).round(6).tobytes() + extra.encode()
    return zlib.crc32(raw)


def run_lineup(
    summary: Summary,
    anomalies: np.ndarray,
    seed: int,
    n_sims: int = N_SIMS,
    steps_per_decade: int = MONTHS_PER_DECADE,
) -> Lineup:
    """The fakes. They have the same missing steps as the real series (`anomalies` is NaN there),
    the real lag-1 autocorrelation, and the spread of the real OLS residuals. `steps_per_decade` is
    120 for months and 10 for years."""
    n = anomalies.size
    valid = np.isfinite(anomalies)
    t = np.arange(n, dtype=float)[valid]
    fit = summary.ols_intercept + summary.ols_slope_per_month * t
    sd = float(np.sqrt(np.mean((anomalies[valid] - fit) ** 2)))
    phi = float(np.clip(summary.r1, 0.0, 0.95))
    rng = np.random.default_rng(seed)
    e_sd = sd * np.sqrt(1.0 - phi**2)
    e = rng.normal(0.0, e_sd, (n_sims, n))
    fakes = lfilter([1.0], [1.0, -phi], e, axis=1) if phi > 0 else e
    sims = np.array([ols_trend(row[valid]).slope for row in fakes]) * steps_per_decade
    obs = summary.ols_per_decade
    beat = int(np.sum(np.abs(sims) >= abs(obs)))
    return Lineup(n_sims, beat, beat / n_sims, obs, sims)


def _later_start_check(
    values: np.ndarray, years: float, sen_sign: float, active: bool, steps_per_year: int = 12
) -> Check:
    """Does the answer survive cutting the first 3, 5 or 8 years? (a trend that only exists in an
    early stretch is not a trend)"""
    bad: list[str] = []
    tried = 0
    for cut in LATER_STARTS:
        if years - cut < MIN_YEARS:
            continue
        tried += 1
        sub = summarise(values[cut * steps_per_year :], "", "later start", steps_per_year)
        if not (np.sign(sub.sen_per_decade) == sen_sign and sub.mk_p_ar1 < LATER_START_P):
            bad.append(f"{cut}")
    if not active:
        return Check("later_start", "Same answer with later start years (no trend to test)", True)
    if tried == 0:
        return Check("later_start", "Same answer with later start years (too short to test)", True)
    if bad:
        return Check(
            "later_start",
            f"The trend changes when the first {' or '.join(bad)} years are left out",
            False,
        )
    return Check("later_start", "Same answer with later start years", True)


def _leave_one_year_out(
    values: np.ndarray, anomalies: np.ndarray, active: bool, steps_per_year: int = 12
) -> Check:
    """Does one year drive the result? Drop each year in turn and refit the slope."""
    if not active:
        return Check("one_year", "No single year drives it (not needed: no trend)", True)
    base = ols_trend(anomalies).slope
    worst_year, worst_change, flips = None, 0.0, False
    spy = steps_per_year
    min_points = 24 if spy == 12 else 5  # two years of months, or five yearly values
    for k in range(int(np.ceil(values.size / spy))):
        keep = anomalies.copy()
        keep[k * spy : k * spy + spy] = np.nan
        if np.isfinite(keep).sum() < min_points:
            continue
        b = ols_trend(keep).slope
        change = abs(b - base) / max(abs(base), 1e-12)
        if change > worst_change:
            worst_year, worst_change, flips = k, change, bool(np.sign(b) != np.sign(base))
    if worst_year is not None and (flips or worst_change >= MAX_CHANGE):
        return Check(
            "one_year",
            f"One year drives it: leaving out year {worst_year + 1} of the window moves the "
            f"slope by {worst_change:.0%}{' and flips its sign' if flips else ''}",
            False,
        )
    return Check("one_year", "No single year drives it", True)


REASONS = {  # a failed check, in plain words (the checks themselves are in `Check.text`)
    "later_start": "it is not clearly there once the earliest years are left out",
    "one_year": "one unusual year drives much of it",
    "instrument_change": "the measuring instrument changed during this period",
    "tests_agree": "the statistical tests do not fully agree",
}


def _amount(x: float) -> str:
    """A slope with sensible digits: 46, 3.2, 0.26."""
    a = abs(x)
    return f"{a:.0f}" if a >= 10 else f"{a:.1f}" if a >= 1 else f"{a:.2f}"


def headline(
    verdict: str,
    assessment: Assessment,
    lineup: Lineup | None,
    checks: list[Check] | tuple[Check, ...],
    summary: Summary,
    unit: str,
    short: bool,
    years: float,
) -> str:
    """One sentence for the top of the result: what was found, and why, in everyday words.

    "Rising trend detected" and "No significant trend detected (yet)" are the repo's wording
    (docs/science-rules.md rule 7); the reason after the colon is plain language. Never says a trend
    is caused by anything."""
    if assessment.verdict == "no_data":
        return "No significant trend detected (yet): there is too little data to judge."
    rate = f"{_amount(summary.ols_per_decade)} {unit} per decade"
    way = "Rising" if summary.ols_per_decade > 0 else "Falling"
    fakes = ""
    if lineup is not None:
        fakes = (
            f"none of {lineup.n_sims:,} random look-alike records were as strong"
            if lineup.beat == 0
            else f"only {lineup.beat} of {lineup.n_sims:,} random look-alike records were as strong"
        )
    if verdict == "detected":
        return (
            f"{way} trend detected: about {rate}. Both statistical tests agree, {fakes}, "
            "and it held up in every check."
        )
    if verdict == "suspect":
        why = " and ".join(REASONS.get(c.code, c.text.lower()) for c in checks if not c.ok)
        if assessment.significant:
            return f"{way} trend found, but treat it with caution: about {rate}, yet {why}."
        return f"A possible trend was found, but treat it with caution: {why}."
    if short:
        return (
            f"No significant trend detected (yet): the record is only {years:.0f} years long and "
            f"at least {MIN_YEARS} are needed to judge a trend."
        )
    if assessment.verdict == "unclear":
        return (
            "No significant trend detected (yet): the two statistical tests disagree, so we "
            "cannot say whether it is rising or falling."
        )
    if assessment.significant and lineup is not None and lineup.share >= ALPHA:
        return (
            "No significant trend detected (yet): the tests find a slope, but "
            f"{lineup.beat} of {lineup.n_sims:,} random look-alike records were just as strong, so "
            "it could be chance."
        )
    close = min(assessment.ols_q, assessment.mk_q) < BORDERLINE_P
    if lineup is not None and (close or lineup.share < ALPHA):
        word = "rise" if summary.ols_per_decade > 0 else "fall"
        seen = (
            f"only {lineup.beat} of {lineup.n_sims:,} random look-alike records were as strong"
            if lineup.share < ALPHA
            else f"{lineup.beat} of {lineup.n_sims:,} random look-alike records were just as strong"
        )
        return (
            f"No significant trend detected (yet), but it is borderline: a {word} of about {rate} "
            f"came close but did not pass the tests, and {seen}. More years of data could "
            "settle it."
        )
    return (
        "No significant trend detected (yet): the data are too noisy to confirm a change of "
        f"about {rate}, so it could be chance."
    )


def judge_case(
    values: np.ndarray,
    unit: str,
    label: str,
    *,
    gap_years: tuple[int, int] | None = None,
    first_year: int = 0,
    leading_pad: int = 0,
    n_sims: int = N_SIMS,
    frequency: str = "monthly",
) -> CaseResult:
    """Judge one monthly series, as monthly months or as yearly averages (`frequency`). `values` is
    always the monthly record: it starts in January (pad the front with NaN), NaN where missing;
    `leading_pad` counts those padding months. `gap_years` is a known change of instrument
    (first_year, last_year of the gap, e.g. GRACE to GRACE-FO 2017 to 2018): when the window holds
    data on both sides of it, a significant trend is `suspect`."""
    if frequency not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {FREQUENCIES}")
    monthly = np.asarray(values, dtype=float)
    spy = 12 if frequency == "monthly" else 1
    if frequency == "monthly":
        y = monthly  # summarise removes the seasonal cycle itself
        summary = summarise(y, unit, label, leading_pad=leading_pad)
        anomalies = deseasonalize(y)
    else:
        y = annual_means(deseasonalize(monthly))  # already seasonal anomalies: no second removal
        summary = summarise(y, unit, label, steps_per_year=1)
        anomalies = y
    assessment = assess_single(summary, label, unit)
    years = summary.n_years
    short = years < MIN_YEARS
    if assessment.verdict == "no_data":
        text = "Too little data to run the tests."
        return CaseResult(
            "not_detected", summary, assessment, None, (), years, None, text, frequency, anomalies,
            headline("not_detected", assessment, None, (), summary, unit, short, years),
        )

    lineup = run_lineup(
        summary, anomalies, _seed(y, f"{label}|{unit}|{frequency}"), n_sims,
        MONTHS_PER_DECADE if spy == 12 else 10,
    )
    noise_ok = lineup.share < ALPHA
    evidence = assessment.significant and noise_ok  # both tests, same sign, and beats the fakes
    any_test = assessment.verdict in ("rise", "fall", "unclear")

    span = (first_year, first_year + (monthly.size - 1) // 12)
    gap_in = bool(gap_years and span[0] < gap_years[0] and span[1] > gap_years[1])
    checks = [
        Check(
            "record_length",
            f"At least {MIN_YEARS} years of record ({years:.0f} chosen)",
            not short,
        ),
        Check(
            "tests_agree",
            "The two tests and the noise lineup agree",
            assessment.verdict != "unclear" and assessment.significant == noise_ok,
        ),
        _later_start_check(y, years, float(np.sign(summary.sen_per_decade)), evidence, spy),
        _leave_one_year_out(y, anomalies, evidence, spy),
        Check(
            "instrument_change",
            f"Instrument change inside the period ({gap_years[0]} to {gap_years[1]})"
            if gap_in and gap_years
            else "No known instrument change in the period",
            not gap_in,
        ),
    ]

    all_ok = all(c.ok for c in checks)
    if short:
        verdict = "not_detected"
    elif evidence and all_ok:
        verdict = "detected"
    elif evidence or (gap_in and any_test):
        verdict = "suspect"
    else:
        verdict = "not_detected"

    needed = None
    if verdict == "not_detected":
        if short:
            needed = float(MIN_YEARS)
        else:
            sigma, phi = noise_params(y, spy)
            needed = years_needed(
                summary.ols_per_decade, sigma, phi, steps_per_year=spy, seed=_seed(y, "needed")
            )
    return CaseResult(
        verdict, summary, assessment, lineup, tuple(checks), years, needed,
        _explain(verdict, assessment, lineup, checks, short),
        frequency, anomalies,
        headline(verdict, assessment, lineup, checks, summary, unit, short, years),
    )


def _explain(verdict: str, a: Assessment, lineup: Lineup, checks: list[Check], short: bool) -> str:
    chance = f"{lineup.beat} of {lineup.n_sims} trend-free fakes were as strong"
    if verdict == "detected":
        return f"{a.explanation} {chance}, and the trend survives every check."
    if verdict == "suspect":
        failed = "; ".join(c.text for c in checks if not c.ok)
        return f"{a.explanation} {chance}. But: {failed}."
    if short:
        return (
            f"Under {MIN_YEARS} years of record: a trend claim is not safe yet. {a.explanation} "
            f"{chance}."
        )
    return f"{a.explanation} {chance}. Not detecting a trend does not mean nothing is changing."
