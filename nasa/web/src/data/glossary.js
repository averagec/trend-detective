// Short, plain-language definitions for the significance numbers shown in the app.
// glossaryFor(labels) returns one line per term that matches a label on screen.
const GLOSSARY = [
  [/^TREND$/i, "Trend", "Is the number going up or down over time? This is how much it changes in 10 years."],
  [/^95% RANGE/i, "95% range", "We are 95% sure the real change lies somewhere in these numbers. If the range crosses zero, we cannot tell whether it is going up or down."],
  [/^OLS/i, "OLS", "A straight line drawn through the dots. Its slope shows how much things change each year."],
  [/MANN-KENDALL/i, "Mann-Kendall", "A check that asks: do the later numbers tend to be bigger than the earlier ones? It does not need a straight line."],
  [/AUTOCORRELATION/i, "Autocorrelation", "Each month is a bit like the month before it. So we have fewer separate pieces of information than it looks like."],
  [/NOISE LINEUP|FAKES/i, "Noise lineup", "We made 1,000 fake records that wiggle randomly but never really change. This counts how many look as strong as ours. Very few means ours is probably real."],
  [/YEARS NEEDED/i, "Years needed", "How many years of data we would need before a change this size would be clear."],
  [/( |^)Q$|^Q-VALUE/i, "Q-value", "Like a p-value, but adjusted for checking lots of places at once. Under 0.05 means it is probably real."],
  [/( |^)P$|^P \(/i, "p-value", "How likely a result this strong is to happen by luck. Under 0.05 means less than 5 in 100, so probably not luck."],
];

export function glossaryFor(labels) {
  const seen = new Set(), rows = [];
  for (const raw of labels) {
    const label = String(raw).trim();
    for (const [re, term, def] of GLOSSARY) {
      if (!seen.has(term) && re.test(label)) {
        seen.add(term);
        rows.push(`<div><b>${term}</b> ${def}</div>`);
      }
    }
  }
  return rows.length ? `<div class="gloss">${rows.join("")}</div>` : "";
}
