// The words for the engine's verdict (core/significance.py, docs/api.md "significance"). MAP.EXE and
// TREND.EXE both use these, so the two pages cannot word the same verdict differently. No statistics
// here: whether a trend is detected comes from the server's `significance.verdict`, never from a
// p-value or a slope checked in the page.

// Long wording: a verdict line in a chart or a sentence heading.
export const VERDICT = {
  rise: "RISING: both tests significant",
  fall: "FALLING: both tests significant",
  unclear: "UNCLEAR: the two tests do not agree",
  none: "NO SIGNIFICANT TREND (YET)",
  no_data: "NOT ENOUGH DATA",
};

// Short wording: a badge, a stat cell or a HUD line.
export const VERDICT_SHORT = {
  rise: "RISING",
  fall: "FALLING",
  unclear: "TESTS DISAGREE",
  none: "NO CLEAR TREND",
  no_data: "NOT ENOUGH DATA",
};

// A trend is detected only as a rise or a fall: both q-values below 0.05 and the two slopes agree.
export const isSignificant = (sig) => !!sig && (sig.verdict === "rise" || sig.verdict === "fall");

// The verdict's word for an unknown value is shown rather than dropped.
export const shortVerdict = (sig) => VERDICT_SHORT[sig.verdict] || String(sig.verdict).toUpperCase();

// The case verdict of the CASES flow (core/lineup.py, docs/api.md "lineup"): the engine's verdict
// plus the noise lineup and the robustness checks. The words only; the page never decides which.
export const CASE_VERDICT = {
  detected: "DETECTED",
  suspect: "SUSPECT",
  not_detected: "NOT YET DETECTABLE",
};
export const CASE_VERDICT_COLOR = { detected: "#2c7a2a", suspect: "#d94a36", not_detected: "#1f4fa0" };
export const CASE_VERDICT_MARK = { detected: "●", suspect: "▲", not_detected: "◌" };
