# 0005 - Spatial selection: a city cell or a radius circle of grid cells

- Status: accepted (2026-11-15, on the team's approval of the plan)
- Builds on: 0003 (pipeline), 0004 (Flask app)

## Context
The team wants to pick a city from a list, or draw a circle on a map, and see the trend of the
grid data behind it. The data are gridded (MERRA-2 about 69 × 55 km, GPCP 55 × 55 km near
Jakarta). A city is usually smaller than one cell, and a circle can cover many cells with very
different trends.

## Decision
- **Per-cell cubes.** `process/cell_cube.py` writes one array per variable for the Indonesia box
  (lon 94 to 142, lat −12 to 7; cell centres inside the box), shaped (months, lat, lon), to
  `data/processed/cells/`. MERRA-2 and GPCP are done; GLDAS and ECCO are not yet.
- **City.** The city is the one cell that contains its point. Each dataset uses its own cell,
  and every result shows that cell's size. A one-cell result carries a scale warning.
- **Circle.** The radius must be 75 to 250 km. A cell is included when its centre lies inside
  the circle (great-circle distance). A circle must hold at least 4 cells.
- **Circle headline.** The spread between cells: how many cells rise or fall significantly, and
  the min and max per-cell slope. A mixed-sign warning appears when significant cells disagree.
  The area average of all used cells is shown below, as a reference.
- **Static cell mask.** A cell with no value in any month is dropped before averaging, so the
  cell set does not change from month to month.
- **Statistics only in `core/`.** Each cell and the average go through `core/summary.summarise`.

## Why 75 to 250 km
- **75 km minimum.** In a sample of 400 random points across Indonesia, every 75 km circle
  contained at least 4 MERRA-2 cell centres (min 4, median 4, max 6). This is a sample, so the
  runtime check still refuses any circle with fewer than 4 cells.
- **4 cells minimum.** A project choice, not a rule from `docs/science-rules.md`. With fewer
  cells there is no usable spread, and min and max do not mean much. Rule 2 in the science rules
  is about record length and does not apply here.
- **250 km maximum.** A 250 km circle covers about 43 to 54 MERRA-2 cells (about 196,000 km²),
  and is wider than the island of Java. Larger circles average over very different climates,
  and science rule 8 says opposite trends should be compared side by side, not averaged.

## Consequences
- The circle average can hide opposite trends. The spread panel exists so that it cannot hide
  them silently.
- A one-cell city result shares its cell with neighbouring places, so the page says so.
- MERRA-2 is a reanalysis and GPCP is a satellite-and-gauge product; neither is station data.
- Cause analysis (step 4 of the user flow) is deferred and is not part of this decision.
- The dashboard is merged into this repository and runs locally. It is not deployed.
- Tests: `tests/process/test_cell_cube.py` (the Jakarta cell reproduces the hand-checked trends),
  `tests/process/test_selection.py` and `tests/app/test_map.py`.
