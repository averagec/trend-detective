# Data sources

One entry per source. Read the entry before touching that source; add quirks you
discover. Use the `data-scout` subagent to explore a new source (keeps raw data out of context).
Prefer **monthly** (then daily) products: these are the easiest according to the brief.

## Candidate sources (from the challenge brief; access details unverified)
| Source | What it gives | Link |
|---|---|---|
| Giovanni (GES DISC) | Variable menus; area-averaged time series, downloadable | https://giovanni.gsfc.nasa.gov/ |
| Hydrology Time Series (GES DISC) | Point time series for hydrology models (e.g. GLDAS) | https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series |
| AppEEARS | Subset/transform land products (e.g. MODIS) to point/area time series | https://appeears.earthdatacloud.nasa.gov/ |
| NOAA Climate Data Online | Station observations for validation | https://www.ncei.noaa.gov/cdo-web/ |
| KNMI Climate Explorer | Reference trend analyses to cross-check our numbers | https://climexp.knmi.nl/ |
| CSA RCM / SWOT | SAR and water-surface data (advanced, probably out of scope) | https://donnees-data.asc-csa.gc.ca/en/dataset/rcm |

Most NASA Earthdata access needs a free Earthdata Login: store it as `EARTHDATA_USERNAME`
/ `EARTHDATA_PASSWORD` in `.env`, never in code.

## Hackathon fallback
Before the demo, cache every demo-case series to `data/demo/` (small CSVs, committed)
so the demo never depends on a live API.

## Entry template
### <Dataset name>
- Provider / link:
- Variable(s), units:
- Access: (env vars) / download
- Resolution (time, space), time range:
- Known quirks:
- Fetched by: `src/trend_detective/ingest/<name>.py` → cached at `data/raw/<name>/`
