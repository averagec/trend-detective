"""One serializer for the significance block every route returns (docs/api.md).

Owns: turning a core.significance.Assessment into plain JSON (NaN becomes null). No statistics here:
every number and the verdict come from core/significance.py.
"""

from __future__ import annotations

import math

from trend_detective.core.significance import ALPHA, Assessment


def _n(x: float | None) -> float | None:
    return None if x is None or not math.isfinite(float(x)) else float(x)


def significance_json(a: Assessment) -> dict:
    return {
        "family": {
            "name": a.family,
            "n_tests": a.n_tests,
            "method": None if a.family == "none" else "benjamini-hochberg",
            "alpha": ALPHA,
        },
        "ols_p": _n(a.ols_p),
        "ols_q": _n(a.ols_q),
        "mk_p_ar1": _n(a.mk_p_ar1),
        "mk_q": _n(a.mk_q),
        "verdict": a.verdict,
        "significant": a.significant,
        "expected_by_chance": _n(a.expected_by_chance),
        "sentence": a.sentence,
        "explanation": a.explanation,
        "warnings": [{"code": code, "text": text} for code, text in a.warnings],
    }
