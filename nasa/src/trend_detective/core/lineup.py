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
VERDICTS = ("detected", "suspect", "not_detected")


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


def _seed(values: np.ndarray, extra: str) -> int:
    """A seed from the data itself: the same record always gets the same lineup."""
    raw = np.nan_to_num(values, nan=-9999.0).round(6).tobytes() + extra.encode()
    return zlib.crc32(raw)


def run_lineup(
    summary: Summary, anomalies: np.ndarray, seed: int, n_sims: int = N_SIMS
) -> Lineup:
    """The fakes. They have the same missing months as the real series (`anomalies` is NaN there),
    the real lag-1 autocorrelation, and the spread of the real OLS residuals."""
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
    sims = np.array([ols_trend(row[valid]).slope for row in fakes]) * MONTHS_PER_DECADE
    obs = summary.ols_per_decade
    beat = int(np.sum(np.abs(sims) >= abs(obs)))
    return Lineup(n_sims, beat, beat / n_sims, obs, sims)


def _later_start_check(values: np.ndarray, years: float, sen_sign: float, active: bool) -> Check:
    """Does the answer survive cutting the first 3, 5 or 8 years? (a trend that only exists in an
    early stretch is not a trend)"""
    bad: list[str] = []
    tried = 0
    for cut in LATER_STARTS:
        if years - cut < MIN_YEARS:
            continue
        tried += 1
        sub = summarise(values[cut * 12 :], "", "later start")
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


def _leave_one_year_out(values: np.ndarray, anomalies: np.ndarray, active: bool) -> Check:
    """Does one year drive the result? Drop each year in turn and refit the slope."""
    if not active:
        return Check("one_year", "No single year drives it (not needed: no trend)", True)
    base = ols_trend(anomalies).slope
    worst_year, worst_change, flips = None, 0.0, False
    for k in range(int(np.ceil(values.size / 12))):
        keep = anomalies.copy()
        keep[k * 12 : k * 12 + 12] = np.nan
        if np.isfinite(keep).sum() < 24:
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


def judge_case(
    values: np.ndarray,
    unit: str,
    label: str,
    *,
    gap_years: tuple[int, int] | None = None,
    first_year: int = 0,
    leading_pad: int = 0,
    n_sims: int = N_SIMS,
) -> CaseResult:
    """Judge one monthly series. `values` starts in January (pad the front with NaN), NaN where
    missing; `leading_pad` counts those padding months. `gap_years` is a known change of instrument
    (first_year, last_year of the gap, e.g. GRACE to GRACE-FO 2017 to 2018): when the window holds
    data on both sides of it, a significant trend is `suspect`."""
    y = np.asarray(values, dtype=float)
    summary = summarise(y, unit, label, leading_pad=leading_pad)
    assessment = assess_single(summary, label, unit)
    years = summary.n_years
    short = years < MIN_YEARS
    if assessment.verdict == "no_data":
        text = "Too little data to run the tests."
        return CaseResult("not_detected", summary, assessment, None, (), years, None, text)

    anomalies = deseasonalize(y)
    lineup = run_lineup(summary, anomalies, _seed(y, f"{label}|{unit}"), n_sims)
    noise_ok = lineup.share < ALPHA
    evidence = assessment.significant and noise_ok  # both tests, same sign, and beats the fakes
    any_test = assessment.verdict in ("rise", "fall", "unclear")

    span = (first_year, first_year + (y.size - 1) // 12)
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
        _later_start_check(y, years, float(np.sign(summary.sen_per_decade)), evidence),
        _leave_one_year_out(y, anomalies, evidence),
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
            sigma, phi = noise_params(y, 12)
            needed = years_needed(summary.ols_per_decade, sigma, phi, seed=_seed(y, "needed"))
    return CaseResult(
        verdict, summary, assessment, lineup, tuple(checks), years, needed,
        _explain(verdict, assessment, lineup, checks, short),
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
