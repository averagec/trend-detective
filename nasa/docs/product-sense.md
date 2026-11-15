# Product sense

Full brief: claude.ai project doc `claude/project-context.md` (source:
https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/).

## Challenge
**Be An Earth System Trend Detective!** (Advanced; Earth Science + Software.)
Build a tool to pick an Earth-science variable (from missions like MODIS, OMI, AIRS, GPM
or models like MERRA-2 and GLDAS), visualise it over time for a region, and answer:
*what* is changing, *where*, *by how much*, and *is it significant*.
Complication: the same variable can trend in opposite directions in different regions.

## Full scope = visualisation + analysis
1. Choose variable(s) with trend potential.
2. Get data for a region.
3. Plot a time series long enough for statistics.
4. Rate of change + significance (t-test / Mann-Kendall / CI).

## Users
High school and college students, plus the public with some science background:
"data detectives". Plain-language variable definitions. A short question flow
(what? where?) leads to suggested variables. Include 2–3 worked demo cases they can watch.

## Award targets (Global, judged by NASA/partner SMEs)
Most relevant: **Best Use of Data**, **Best Use of Science**, **Best Use of Storytelling**,
Best Use of Technology, Galactic Impact. Local judging historically: Impact, Creativity,
Validity, Relevance, Presentation (re-check the 2026 Judging and Awards Guide).
Trade-off rule: scientific correctness > a polished demo case > more features.

## Scope guardrails
- Must-have: variable + region selection, time-series plot, deseasonalised trend with
  significance, plain-language result sentence, ≥2 demo case studies.
- Nice-to-have: AI-suggested variables or regions, side-by-side regional comparison, maps.
- Out of scope: non-linear and complex models, hourly data, building our own data archive.

## Status
Hackathon live Nov 14–15 2026 (48h). Idea shortlist pending three reviews
(engineer, NASA scientist, professor). Fill in the chosen concept here once it's decided.

## Deliverables (confirm in the 2026 guide)
Project page/write-up, demo video, repo/live link: _deadlines TODO_.
