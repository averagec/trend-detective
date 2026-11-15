# 0006 - Flood and drought flow for one city

- Status: proposed (2026-11-15), for the team's approval before the commit
- Builds on: 0004 (Flask app), 0005 (cell cubes and selection)

## Context
The updated user flow (city level):
1. Pick the incident: flood or drought.
2. Pick the city from a fixed list, each with coordinates and a rainfall source.
3. Pick the period: a month or a year.
4. The tool answers: trend or one-time event? where and when? by how much (amount and percent)?
   which factors moved alongside, and by how much? Factors are co-movement, not causes.

## Decision
- **Rainfall source per city.** The city list (`data/catalog/cities_idn.csv`) gets a
  `rainfall_source` column: `merra2:precip` or `gpcp:gpcp_precip`. The loader refuses any other value.
- **Where.** The one grid cell that contains the city (0005). Each result names the dataset and
  the cell's size.
- **When.** For a month, that month. For a year, the month in the year with the strongest signal
  (the highest percentile for a flood, the lowest for a drought).
- **Flood and drought.** Defined only by rainfall in this record: a flood is unusually heavy
  rainfall, a drought is unusually little. Neither measures river, street or soil conditions.
- **Extreme.** The period total sits at or above the 90th percentile (flood) or at or below the
  10th (drought), against the same calendar month (monthly periods) or the complete annual totals
  (yearly periods). The thresholds are constants in `core/events.py`.
- **Trend.** OLS on the deseasonalised monthly rainfall rate, with the autocorrelation adjustment
  (`core/trend.py`). A trend is reported only when significant at 95%.
- **The call.**
  - Not extreme → "not unusual".
  - Extreme and a significant trend in the same direction → "extreme, in line with a trend".
  - Extreme with no same-direction trend → "one-time event".
- **Amount.** Observed total minus the climatological median (monthly or annual), in mm and in
  percent, with the rank against the record.
- **Co-movement.** Each factor's deseasonalised monthly anomalies are correlated with rainfall
  over the months both series share, with the same autocorrelation adjustment. The response
  gives r, p, the months shared, the factor's change in the period, and the rain change implied
  by the least-squares slope. Every factor carries the note "moved together, not a cause".
- **Factors.** MERRA-2 temperature, humidity, pressure, evaporation, land surface temperature and
  vapour pressure deficit (same grid cell); the NASA sea-surface height indicators for ENSO, IOD
  and PDO (monthly means from 1993). The rainfall variables themselves are never factors.

## Why
- The user wants answers at the city level, from the same data and statistics as the rest of
  the project. Using the cell that contains the city keeps the city answer on the same footing as
  the one-cell city result in 0005.
- Percentiles against the same calendar month separate a wet month from a wet season. The trend
  test keeps the long-term change apart from a single extreme.
- Co-movement is a correlation over the record, not a model of cause. Calling it a cause would
  break science rules 7 and 8.

## Consequences
- The reanalysis and satellite products may understate city-scale extremes. The February 2007
  Jakarta flood sits at about the 89th percentile of February totals in this record, so it is
  not called extreme at the 90th-percentile threshold. The threshold is a decision for the team.
- Several factors are tested at once, and the p-values are not corrected for that. The page shows
  the months shared and the correlations, and says so in the docs. A correction (for example
  Benjamini-Hochberg) is not yet in the code.
- The NASA sea-surface height indicators cover 1993 onward, so their co-movement uses a shorter
  record than the MERRA-2 factors. The months shared are shown for each factor.
- GLDAS rainfall and soil moisture are not in the cell cubes yet, so they are not used as a
  rainfall source or a factor.
- Tests: `tests/core/test_events.py` (golden), `tests/process/test_event_series.py`,
  `tests/app/test_event.py`.
