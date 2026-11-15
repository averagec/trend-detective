"""The significance engine: summaries in, one verdict out. Pure functions: no I/O, no network.

Owns: correcting for the number of series tested (Benjamini-Hochberg, one family at a time), the
verdict ladder ("both tests, after correction"), and the sentence built from the verdict. It never
computes a trend itself: every slope, CI and p-value comes from `core.summary.summarise`.

The trend engine (process/) chooses cells, regions and averages and hands over series; this module
decides what counts as significant. Rules: docs/decisions/0009-significance-engine-*.md and
docs/science-rules.md (rule 7: only the two phrases "statistically significant at 95%" and
"no significant trend detected (yet)").

Families (which tests are corrected together):
  "layer"  one variable across regions (the map, TREND.EXE)
  "circle" the cells of one circle
  "none"   a single series (a city, a pasted series): the plain p-values, no correction
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from trend_detective.core.summary import Summary
from trend_detective.core.trend import benjamini_hochberg

ALPHA = 0.05
FAMILIES = ("layer", "circle", "none")
CHANCE_PER_DIRECTION = ALPHA / 2  # share of null series that look significant on one side


@dataclass(frozen=True)
class Item:
    """One series ready to be judged: its summary and the words used in its sentence."""

    summary: Summary
    label: str
    unit: str


@dataclass(frozen=True)
class Assessment:
    family: str  # "layer", "circle" or "none"
    n_tests: int | None  # series with a p-value in the family; None for a single series
    ols_p: float
    ols_q: float  # Benjamini-Hochberg adjusted (equal to ols_p when there is no family)
    mk_p_ar1: float  # autocorrelation-adjusted Mann-Kendall p-value (ADR 0007)
    mk_q: float
    verdict: str  # "rise", "fall", "unclear", "none" or "no_data"
    significant: bool  # the verdict is "rise" or "fall"
    expected_by_chance: float | None  # series per direction that would look significant by luck
    sentence: str
    warnings: tuple[tuple[str, str], ...]  # (machine code, text)


def warning_code(text: str) -> str:
    """A stable code for a warning text, so pages do not match on wording."""
    if text.startswith("Only"):
        return "short_record"
    if "missing" in text:
        return "missing_months"
    if "tests disagree" in text:
        return "tests_disagree"
    if "not enough data" in text:
        return "not_enough_data"
    return "note"


def verdict_for(
    ols_q: float, mk_q: float, ols_slope: float, sen_slope: float, alpha: float = ALPHA
) -> str:
    """The ladder: rise or fall only when both q-values are below alpha and the slopes agree.

    One test significant, or both with opposite signs: "unclear". Neither: "none". A missing p-value
    (too little data) is "no_data".
    """
    if not (np.isfinite(ols_q) and np.isfinite(mk_q)):
        return "no_data"
    ols_sig, mk_sig = ols_q < alpha, mk_q < alpha
    if ols_sig and mk_sig:
        same_sign = ols_slope != 0 and np.sign(ols_slope) == np.sign(sen_slope)
        if not same_sign:
            return "unclear"
        return "rise" if ols_slope > 0 else "fall"
    if ols_sig or mk_sig:
        return "unclear"
    return "none"


def _sentence(item: Item, verdict: str, family: str, n_tests: int | None) -> str:
    s = item.summary
    if verdict == "no_data":
        return s.sentence  # "... not enough data for a trend ..."
    if verdict in ("rise", "fall"):
        verb = "rose" if verdict == "rise" else "fell"
        ci = s.ols_ci_per_decade
        corrected = family != "none" and n_tests is not None and n_tests > 1
        suffix = f" after correcting for {n_tests} tests at once" if corrected else ""
        return (
            f"{item.label} {verb} by {abs(s.ols_per_decade):.2f} {item.unit} per decade "
            f"(95% CI {ci[0]:+.2f} to {ci[1]:+.2f}), statistically significant at 95%{suffix}."
        )
    return (
        f"{item.label}: no significant trend detected (yet). "
        f"The estimated change is {s.ols_per_decade:+.2f} {item.unit} per decade."
    )


def _warnings(item: Item, verdict: str, ols_q: float, mk_q: float) -> tuple[tuple[str, str], ...]:
    # The summary's "tests disagree" note is about the uncorrected p-values; the ladder says it
    # again after correction, so the stale one is left out.
    out = [(warning_code(w), w) for w in item.summary.warnings if "tests disagree" not in w]
    if verdict == "unclear":
        if ols_q < ALPHA and mk_q < ALPHA:
            out.append((
                "tests_disagree",
                "Both tests are significant but the slopes have opposite signs: check for outliers "
                "or a non-linear pattern before trusting it.",
            ))
        else:
            out.append((
                "one_test_significant",
                "Only one of the two tests is significant after correction: check for outliers or "
                "a non-linear pattern before trusting it.",
            ))
    return tuple(out)


def assess_family(items: Sequence[Item], family: str) -> list[Assessment]:
    """Judge every series of one family together. The result is in the order of `items`.

    The OLS p-values and the adjusted Mann-Kendall p-values are each corrected with
    Benjamini-Hochberg across the family. Series without a p-value are not counted as tests.
    """
    if family not in FAMILIES:
        raise ValueError(f"family must be one of {FAMILIES}")
    if family == "none" and len(items) != 1:
        raise ValueError('family "none" is for a single series')
    ols_p = np.array([it.summary.ols_p for it in items], dtype=float)
    mk_p = np.array([it.summary.mk_p_ar1 for it in items], dtype=float)
    if family == "none":
        ols_q, mk_q, n_tests = ols_p.copy(), mk_p.copy(), None
    else:
        ols_q, mk_q = benjamini_hochberg(ols_p), benjamini_hochberg(mk_p)
        n_tests = int(np.isfinite(ols_p).sum())
    chance = None if n_tests is None else CHANCE_PER_DIRECTION * n_tests

    out = []
    for k, item in enumerate(items):
        s = item.summary
        verdict = verdict_for(ols_q[k], mk_q[k], s.ols_per_decade, s.sen_per_decade)
        out.append(
            Assessment(
                family=family,
                n_tests=n_tests,
                ols_p=float(ols_p[k]),
                ols_q=float(ols_q[k]),
                mk_p_ar1=float(mk_p[k]),
                mk_q=float(mk_q[k]),
                verdict=verdict,
                significant=verdict in ("rise", "fall"),
                expected_by_chance=chance,
                sentence=_sentence(item, verdict, family, n_tests),
                warnings=_warnings(item, verdict, float(ols_q[k]), float(mk_q[k])),
            )
        )
    return out


def assess_single(summary: Summary, label: str, unit: str) -> Assessment:
    """One series on its own (a city, a pasted series): the ladder on the plain p-values."""
    return assess_family([Item(summary, label, unit)], "none")[0]
