// The words and the one rule for a detected trend, shared by MAP.EXE and TREND.EXE (docs/api.md).
// Run: npm test
import test from "node:test";
import assert from "node:assert/strict";
import { VERDICT, VERDICT_SHORT, isSignificant, shortVerdict } from "../src/data/verdict-wording.js";

const VERDICTS = ["rise", "fall", "unclear", "none", "no_data"];

test("only a rise or a fall is a detected trend", () => {
  assert.equal(isSignificant({ verdict: "rise" }), true);
  assert.equal(isSignificant({ verdict: "fall" }), true);
  for (const verdict of ["unclear", "none", "no_data", "surprise"]) {
    assert.equal(isSignificant({ verdict }), false, verdict);
  }
  assert.equal(isSignificant(undefined), false);
  assert.equal(isSignificant(null), false);
});

test("every verdict has a long and a short wording, with no undefined left in", () => {
  for (const verdict of VERDICTS) {
    assert.ok(VERDICT[verdict], `long: ${verdict}`);
    assert.ok(VERDICT_SHORT[verdict], `short: ${verdict}`);
    assert.equal(shortVerdict({ verdict }), VERDICT_SHORT[verdict]);
  }
});

test("an unknown verdict is shown, not dropped", () => {
  assert.equal(shortVerdict({ verdict: "surprise" }), "SURPRISE");
});

test("the long wording is the one TREND.EXE has always shown", () => {
  assert.equal(VERDICT.rise, "RISING: both tests significant");
  assert.equal(VERDICT.unclear, "UNCLEAR: the two tests do not agree");
  assert.equal(VERDICT.none, "NO SIGNIFICANT TREND (YET)");
});
