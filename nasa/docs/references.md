# References for the data sources

Compiled 2026-11-15 from the metadata inside the files in `data/raw/` (global attributes and file
headers) and from PO.DAAC / GES DISC landing pages. Replace `[access date]` with the date you
retrieve each dataset when you cite it.

Items marked **[confirm]** were not checked against the official landing page. Check them before the
final report.

---

## 1. MERRA-2 reanalysis (NASA GMAO), version 5.12.4

**Method paper (cite once):**
Gelaro, R., McCarty, W., Suárez, M. J., et al. (2017). The Modern-Era Retrospective Analysis for
Research and Applications, Version 2 (MERRA-2). *Journal of Climate*, 30(14), 5419–5454.
https://doi.org/10.1175/JCLI-D-16-0758.1

**Dataset citations (one per collection we use):**

| Collection | Variables | Citation | DOI |
|---|---|---|---|
| M2SDNXSLV | T2MMAX (daily max 2 m air temperature) | Global Modeling and Assimilation Office (GMAO) (2015). MERRA-2 statD_2d_slv_Nx: 2d, Daily, Aggregated Statistics, Single-Level, Assimilation, Single-Level Diagnostics, version 5.12.4. NASA GES DISC. [confirm year] | [10.5067/9SC1VNTWGWV3](https://doi.org/10.5067/9SC1VNTWGWV3) |
| M2TMNXSLV | T2M, QV2M, PS | GMAO (2015). MERRA-2 tavg1_2d_slv_Nx: 2d, 1-Hourly, Time-Averaged, Single-Level, Assimilation, Single-Level Diagnostics Monthly Mean, version 5.12.4. NASA GES DISC. [confirm year] | [10.5067/AP1B0BA5PD2K](https://doi.org/10.5067/AP1B0BA5PD2K) |
| M2TMNXFLX | EVAP, PRECTOTCORR | GMAO (2015). MERRA-2 tavg1_2d_flx_Nx: 2d, 1-Hourly, Time-Averaged, Single-Level, Assimilation, Surface Flux Diagnostics Monthly Mean, version 5.12.4. NASA GES DISC. [confirm year] | [10.5067/0JRLVL8YV2Y4](https://doi.org/10.5067/0JRLVL8YV2Y4) |
| M2TMNXLND | TSURF | GMAO (2015). MERRA-2 tavg1_2d_lnd_Nx: 2d, 1-Hourly, Time-Averaged, Single-Level, Assimilation, Land Surface Diagnostics Monthly Mean, version 5.12.4. NASA GES DISC. [confirm year] | [10.5067/8S35XF81C28F](https://doi.org/10.5067/8S35XF81C28F) |

Accessed through NASA Harmony subsetting (https://harmony.earthdata.nasa.gov). Granules are
searched through NASA CMR (https://cmr.earthdata.nasa.gov).

---

## 2. GLDAS Noah land surface model, monthly 0.25° (GLDAS_NOAH025_M, v2.1)

**Method paper (cite once):**
Rodell, M., Houser, P. R., Jambor, U., et al. (2004). The Global Land Data Assimilation System.
*Bulletin of the American Meteorological Society*, 85(3), 381–394.
https://doi.org/10.1175/BAMS-85-3-381

**Dataset citation:**
Beaudoing, H., and Rodell, M. (2020). GLDAS Noah Land Surface Model L4 monthly 0.25 x 0.25 degree
V2.1 (GLDAS_NOAH025_M). NASA Goddard Earth Sciences Data and Information Services Center (GES DISC).
https://doi.org/10.5067/SXAVCZFAQLNO [confirm authors and year on the GES DISC page; the DOI comes
from catalog listings, not from the file]

Model and forcing references listed in the file's `references` attribute: Kumar et al. (2006,
*Environmental Modelling & Software*) and Peters-Lidard et al. (2007, ISSE) [confirm full citations].

Note: use the main-stream DOI above, not the Early Product (`GLDAS_NOAH025_M_EP`, DOI
10.5067/5OVHMFF2IAV3).

---

## 3. GPCP precipitation, monthly 0.5° (GPCPMON, v3.3)

**Method paper (cite once):**
Adler, R. F., Huffman, G. J., Chang, A., et al. (2003). The Version-2 Global Precipitation
Climatology Project (GPCP) Monthly Precipitation Analysis (1979–Present). *Journal of
Hydrometeorology*, 4(6), 1147–1167.
https://doi.org/10.1175/1525-7541(2003)004<1147:TVGPCP>2.0.CO;2
(This is the GPCP method paper. Version 3.3 is a later release of the same product line.)

**Dataset citation:**
Huffman, G. J., and Bolvin, D. T. (2025). GPCP Precipitation Level 3 Monthly 0.5-Degree V3.3
(GPCPMON). NASA GES DISC. https://doi.org/10.5067/MEASURES/GPCP/DATA306 [confirm the author list
against the GES DISC suggested citation; the file names Huffman and Bolvin as creators, release date
2025-01-31]

Variable used: `sat_gauge_precip` (combined satellite and gauge estimate). The file's own `References`
attribute reads "Data set references will be provided", so the paper above is the method reference.

---

## 4. GRACE and GRACE-FO JPL mascon solution, RL06.3 V04

**Method papers (cite both):**
- Watkins, M. M., Wiese, D. N., Yuan, D.-N., Boening, C., and Landerer, F. W. (2015). Improved methods
  for observing Earth's time variable mass distribution with GRACE using spherical cap mascons.
  *Journal of Geophysical Research: Solid Earth*, 120. https://doi.org/10.1002/2014JB011547
- Wiese, D. N., Landerer, F. W., and Watkins, M. M. (2016). Quantifying and reducing leakage errors in
  the JPL RL05M GRACE mascon solution. *Water Resources Research*.
  https://doi.org/10.1002/2016WR019344 [confirm title; cited for the CRI filter and gain factors]

**Dataset citation:**
Wiese, D. N., Yuan, D.-N., Boening, C., Landerer, F. W., and Watkins, M. M. JPL GRACE and GRACE-FO
Mascon Ocean, Ice, and Hydrology Equivalent Water Height, JPL Release 06.3, Version 04 (RL06.3Mv04).
PO.DAAC, CA, USA. https://doi.org/10.5067/TEMSC-3MJ634 [confirm the author list on the PO.DAAC page;
the file's `creator_name` is David Wiese]

The file in `data/raw/witness/grace/all/` is `GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04.nc`.
The filename matches the non-CRI grid product, so the DOI above should apply. [confirm]
The CRI-filtered sibling product has DOI 10.5067/TEMSC-3JC634. PO.DAAC recommends the CRI version for
most users.

---

## 5. ECCO sea surface height, monthly mean (V4r4 and V4r4b)

**Method and state-estimate references (cite once each):**
- Forget, G., Campin, J.-M., Heimbach, P., Hill, C. N., Ponte, R. M., and Wunsch, C. (2015). ECCO
  version 4: an integrated framework for non-linear inverse modeling and global ocean state
  estimation. *Geoscientific Model Development*, 8, 3071–3104.
  https://doi.org/10.5194/gmd-8-3071-2015
- ECCO Consortium, Fukumori, I., Wang, O., Fenty, I., Forget, G., Heimbach, P., and Ponte, R. M. (2020).
  Synopsis of the ECCO Central Production Global Ocean and Sea-Ice State Estimate (Version 4 Release 4).
  https://doi.org/10.5281/zenodo.3765928 (from the file's `references` attribute)

**Dataset citations:**

| Product in our data | Citation | DOI |
|---|---|---|
| ECCO V4r4, 0.5° lat-lon (`ECCO_L4_SSH_05DEG_MONTHLY_V4R4`) | ECCO Consortium, Fukumori, I., Wang, O., Fenty, I., Forget, G., Heimbach, P., and Ponte, R. M. (2021). ECCO Sea Surface Height – Monthly Mean 0.5 Degree (Version 4 Release 4). PO.DAAC. | [10.5067/ECG5M-SSH44](https://doi.org/10.5067/ECG5M-SSH44) |
| ECCO V4r4b, 0.5° lat-lon (`ECCO_L4_SSH_05DEG_MONTHLY_V4R4B`) | ECCO Consortium et al. (2021). ECCO Sea Surface Height – Monthly Mean 0.5 Degree (Version 4 Release 4b). PO.DAAC. | [10.5067/ECG5M-SSH4B](https://doi.org/10.5067/ECG5M-SSH4B) |
| ECCO V4r4, native LLC90 grid (`ECCO_L4_SSH_LLC0090GRID_MONTHLY_V4R4`) | ECCO Consortium et al. (2021). ECCO Sea Surface Height – Monthly Mean llc90 Grid (Version 4 Release 4). PO.DAAC. | [confirm DOI on PO.DAAC] |
| ECCO V4r4b, native LLC90 grid (`ECCO_L4_SSH_LLC0090GRID_MONTHLY_V4R4B`) | ECCO Consortium et al. (2021). ECCO Sea Surface Height – Monthly Mean llc90 Grid (Version 4 Release 4b). PO.DAAC. | [confirm DOI on PO.DAAC] |

V4r4b is an errata release of V4r4. The file's `history` attribute says so.

---

## 6. NASA SSH sea surface height indicators (ENSO, IOD, PDO, GMSL)

**Dataset citations (one per indicator, Version 1):**
- NASA-SSH (2025). NASA-SSH ENSO Sea Surface Height Indicator, Version 1. PO.DAAC, CA, USA.
  https://doi.org/10.5067/NSIND-ENSV1
- NASA-SSH (2025). NASA-SSH IOD Sea Surface Height Indicator, Version 1. PO.DAAC, CA, USA.
  https://doi.org/10.5067/NSIND-IODV1
- NASA-SSH (2025). NASA-SSH PDO Sea Surface Height Indicator, Version 1. PO.DAAC, CA, USA.
  https://doi.org/10.5067/NSIND-PDOV1 [confirm author line; the PO.DAAC PDO page may credit individual
  authors]
- NASA-SSH (2025). NASA-SSH Global Mean Sea Level from Simple Gridded Sea Surface Height, Version 1.
  PO.DAAC, CA, USA. https://doi.org/10.5067/NSIND-GMSV1

The `[YYYY-MM-DD]` access-date placeholder in the file headers should be filled in when you cite.

**Source data:** NASA-SSH Simple Gridded Sea Surface Height from Standardized Reference Missions Only,
Version 1.1. https://podaac.jpl.nasa.gov/dataset/NASA_SSH_REF_SIMPLE_GRID_V11 [confirm the DOI for
v1.1; the search result gave 10.5067/NSREF-SG0V1 for version 1]

**Method papers (named in the file headers):**
- Kim, K. Y., Hamlington, B., and Na, H. (2015). Theoretical foundation of cyclostationary EOF analysis
  for geophysical and climatic variables: concepts and examples. *Earth-Science Reviews*, 150, 201–218.
- Kumar, P., Hamlington, B., Cheon, S., Han, W., and Thompson, P. (2020). 20th century multivariate
  Indian Ocean regional sea level reconstruction. *Journal of Geophysical Research: Oceans*, 125(10).
  https://doi.org/10.1029/2020JC016270
- Hamlington, B. D., et al. (2019). *Journal of Geophysical Research: Oceans*.
  https://doi.org/10.1029/2018JC014635 [confirm full author list]

---

## 7. Sentinel-1 SAR scene list and browse images

Copernicus Sentinel-1 data (2024), processed by ESA, retrieved from the Alaska Satellite Facility
(ASF) datapool. https://datapool.asf.alaska.edu [confirm the ASF-suggested citation string]

Only the scene list (`data/raw/sar/scenes.csv`, 20 scenes) and the browse images are on disk. The
SAR data itself has not been downloaded.

---

## 8. GDIS, Global Dataset of Geocoded Disaster Locations (not yet in `datasets.md`)

Rosvold, E. L., and Buhaug, H. (2021). GDIS, a global dataset of geocoded disaster locations.
*Scientific Data*, 8, 61. https://doi.org/10.1038/s41597-021-00846-6

The files in `data/raw/human_dimensions/gdis/` are the PEND-GDIS 1960–2018 release. This dataset is
not yet listed in `docs/datasets.md` and has not been cleaned.

---

## 9. Statistical methods (used in `core/trend.py`)

- Santer, B. D., et al. (2000). Statistical significance of trends and trend differences in
  layer-average atmospheric temperature time series. *Journal of Geophysical Research*, 105(D6),
  7337–7356. https://doi.org/10.1029/1999JD901105 [confirm]
  (effective sample size correction for lag-1 autocorrelation)
- Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13, 245–259.
- Kendall, M. G. (1975). *Rank Correlation Methods*. Charles Griffin.
- Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *Journal of the
  American Statistical Association*, 63(324), 1379–1389.
- Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate: a practical and
  powerful approach to multiple testing. *Journal of the Royal Statistical Society: Series B*, 57(1),
  289–300.

---

## Open items before the final report

1. Confirm every **[confirm]** item above on the landing page or in the paper.
2. Add GDIS to `docs/datasets.md`, or drop it from the project if it is not used.
3. Confirm the DOIs for the two LLC90 ECCO products on PO.DAAC.
4. Replace all `[access date]` and `[YYYY-MM-DD]` placeholders with the retrieval dates.
