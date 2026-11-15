"""pull_nasa.py: fetch every demo dataset programmatically (no manual downloads).

Belongs in the harness `ingest/` module, the only module allowed network calls.
Writes tidy monthly CSVs (date,value) to data/raw/<source>/ and a provenance JSON per file.
The app and core/ then run offline from those files.

Status of each source (14 Nov 2026):
  POWER    VERIFIED from team laptop (no login)
  TESViS   documented REST API, NOT yet run by us (no login for /subset per docs)
  earthaccess (GPCP, GLDAS, GRACE, MERRA-2 aerosol): documented library, NOT yet run by us
           (needs Earthdata Login: run `earthaccess.login(persist=True)` once, or set
            EARTHDATA_USERNAME / EARTHDATA_PASSWORD; never commit credentials)

Usage examples:
  python ingest/pull_nasa.py power  --lat 1.35 --lon 103.9 --params T2M --start 1981 --end 2024
  python ingest/pull_nasa.py tesvis --lat 1.35 --lon 103.8 --product MOD13Q1 --band 250m_16_days_NDVI --start 2000 --end 2024
  python ingest/pull_nasa.py earthaccess --short-name GPCPMON --version 3.3 --var <name> --bbox 100 -1 106 4 --start 1983 --end 2023
  python ingest/pull_nasa.py earthaccess --short-name GPCPMON --version 3.3 --list-vars      # discover variable names first
"""
import argparse
import csv
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

import requests

RAW = Path("data/raw")


def _save(source, name, rows, meta):
    out = RAW / source
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "value"])
        w.writerows(rows)
    meta = {**meta, "rows": len(rows), "accessed": dt.datetime.now(dt.timezone.utc).isoformat()}
    (out / f"{name}.provenance.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {path} ({len(rows)} rows)")
    return path


# ---------------------------------------------------------------- NASA POWER (verified)
def power(lat, lon, params, start, end, community="RE"):
    url = "https://power.larc.nasa.gov/api/temporal/monthly/point"
    q = dict(parameters=",".join(params), community=community, latitude=lat, longitude=lon,
             start=start, end=end, format="JSON")
    r = requests.get(url, params=q, timeout=120)
    r.raise_for_status()
    j = r.json()
    fill = j["header"].get("fill_value", -999)
    for p in params:
        series = j["properties"]["parameter"][p]
        rows = [(f"{k[:4]}-{k[4:]}-01", v) for k, v in series.items()
                if not k.endswith("13") and v != fill]          # YYYY13 = annual mean -> drop
        _save("power", f"{p}_{lat}_{lon}_{start}_{end}", rows, dict(
            source="NASA POWER monthly point", url=r.url, units=j["parameters"][p]["units"],
            note="YYYY13 annual keys dropped; PRECTOTCORR after 2020 is SUSPECT (step change)"))


# ---------------------------------------------------------------- ORNL TESViS (MODIS/VIIRS land)
TESVIS = "https://modis.ornl.gov/rst/api/v1"


def tesvis(lat, lon, product, band, start, end, km=0):
    """Point (or up to 100 km box) time series. API returns max 10 dates per call, so loop."""
    h = {"Accept": "application/json"}
    dates = requests.get(f"{TESVIS}/{product}/dates", params=dict(latitude=lat, longitude=lon),
                         headers=h, timeout=60).json()["dates"]
    dates = [d for d in dates if start <= int(d["calendar_date"][:4]) <= end]
    rows, scale = [], None
    for i in range(0, len(dates), 10):
        chunk = dates[i:i + 10]
        r = requests.get(f"{TESVIS}/{product}/subset", headers=h, timeout=120, params=dict(
            latitude=lat, longitude=lon, band=band, startDate=chunk[0]["modis_date"],
            endDate=chunk[-1]["modis_date"], kmAboveBelow=km, kmLeftRight=km))
        r.raise_for_status()
        j = r.json()
        scale = float(j.get("scale") or 1)
        for s in j["subset"]:
            vals = [v for v in s["data"] if v is not None and v > -2000]   # drop fill values
            if vals:
                rows.append((s["calendar_date"], sum(vals) / len(vals) * scale))
        time.sleep(0.5)  # be polite
    _save("tesvis", f"{product}_{band}_{lat}_{lon}_km{km}_{start}_{end}", rows, dict(
        source="ORNL DAAC TESViS REST", product=product, band=band, scale=scale, km=km,
        note="16-day composites: aggregate to monthly in core; QA filtering not yet applied",
        citation="ORNL DAAC. 2018. TESViS RESTful Web Service. doi:10.3334/ORNLDAAC/1600"))


# ---------------------------------------------------------------- earthaccess (gridded, login)
def earthaccess_monthly(short_name, version, var, bbox, start, end, list_vars=False,
                        group=None, level=None, level_dim=None, tag=""):
    """Stream granules lazily, cut the bbox, cos(lat)-weighted mean -> one value per time step.
    group: HDF5 group holding the variable (e.g. 'Grid' for GPM IMERG).
    level: pressure level to select (e.g. 850 or 1 hPa for MERRA-2 M2IMNPASM)."""
    import earthaccess
    import numpy as np
    import xarray as xr
    earthaccess.login()  # uses .netrc / env vars / prompt
    res = earthaccess.search_data(short_name=short_name, version=version,
                                  temporal=(f"{start}-01-01", f"{end}-12-31"),
                                  bounding_box=tuple(bbox))
    print(f"{len(res)} granules for {short_name} v{version}")
    if not res:
        sys.exit("No granules: check short name/version on search.earthdata.nasa.gov")
    files = earthaccess.open(res)
    kw = {"group": group} if group else {}
    if list_vars:
        ds = xr.open_dataset(files[0], **kw)
        print(ds)
        return
    W, S, E, N = bbox
    rows = []
    for f in files:
        ds = xr.open_dataset(f, **kw)
        if level is not None:
            ld = level_dim or next(n for n in ("lev", "level", "plev", "StdPressureLev", "TempPrsLvls_A")
                                   if n in ds.coords or n in ds.dims)
            ds = ds.sel({ld: level}, method="nearest")
        latn = next(n for n in ("lat", "latitude", "Latitude") if n in ds.coords)
        lonn = next(n for n in ("lon", "longitude", "Longitude") if n in ds.coords)
        if float(ds[lonn].max()) > 180:               # 0..360 grid -> -180..180 so any box works
            ds = ds.assign_coords({lonn: ((ds[lonn] + 180) % 360) - 180}).sortby(lonn)
        la = ds[latn]
        lat_slice = slice(S, N) if la[0] < la[-1] else slice(N, S)
        sub = ds[var].sel({latn: lat_slice, lonn: slice(W, E)})
        w = np.cos(np.deg2rad(sub[latn]))
        val = sub.weighted(w).mean(dim=[latn, lonn], skipna=True)
        for t in (val["time"].values if "time" in val.dims else [None]):
            v = float(val.sel(time=t)) if t is not None else float(val)
            date = str(t)[:10] if t is not None else "unknown"
            if not math.isnan(v):
                rows.append((date, v))
    rows.sort()
    lev = f"_L{level}" if level is not None else ""
    name = tag or f"{short_name}_{version}_{var}{lev}_{'_'.join(map(str, bbox))}_{start}_{end}"
    _save("earthaccess", name, rows, dict(
        source="NASA Earthdata via earthaccess", short_name=short_name, version=version, var=var,
        group=group, level=level, bbox_WSEN=bbox,
        method="cos(lat)-weighted area mean of grid cells inside bbox"))


# ---------------------------------------------------------------- catalog mapped to the challenge
# Every entry ties to the challenge background: named instrument/model, variable type, and realm
# (land / ocean / atmospheric level). verified = we have confirmed the variable name ourselves.
# Run `pull_nasa.py earthaccess ... --list-vars` once for every entry with verified=False.
SG = (1.35, 103.9)
SEA_BOX = [100, -1, 106, 4]            # Singapore / Johor / Riau
N_INDIA = [73, 24, 82, 32]             # Punjab-Haryana-Rajasthan (GRACE scale: several mascons)
SCS = [108, 5, 118, 15]                # South China Sea (ocean)
CATALOG = {
    # --- simple variables
    "sg_t2m":        dict(how="power", src="MERRA-2 (via POWER)", realm="land/air", params=["T2M"], start=1981, end=2024, verified=True),
    "sea_rain_gpcp": dict(how="ea", src="GPCP (satellite+gauge)", realm="land", short_name="GPCPMON", version="3.3", var="sat_gauge_precip", bbox=SEA_BOX, start=1983, end=2023, verified=False),
    "sea_rain_gpm":  dict(how="ea", src="GPM IMERG", realm="land", short_name="GPM_3IMERGM", version="07", var="precipitation", group="Grid", bbox=SEA_BOX, start=2001, end=2024, verified=False,
                          note="IMERG is not a climate data record: cross-check only"),
    # --- complex variables (land model)
    "india_evap":    dict(how="ea", src="GLDAS Noah 2.1", realm="land", short_name="GLDAS_NOAH025_M", version="2.1", var="Evap_tavg", bbox=N_INDIA, start=2000, end=2024, verified=False),
    "india_runoff":  dict(how="ea", src="GLDAS Noah 2.1", realm="land", short_name="GLDAS_NOAH025_M", version="2.1", var="Qs_acc", bbox=N_INDIA, start=2000, end=2024, verified=False,
                          note="surface runoff = streamflow proxy; add Qsb_acc for subsurface"),
    "india_soilm":   dict(how="ea", src="GLDAS Noah 2.1", realm="land", short_name="GLDAS_NOAH025_M", version="2.1", var="SoilMoi0_10cm_inst", bbox=N_INDIA, start=2000, end=2024, verified=False),
    # --- MODIS (land surface)
    "sg_ndvi":       dict(how="tesvis", src="MODIS Terra", realm="land", product="MOD13A3", band="1_km_monthly_NDVI", lat=1.35, lon=103.8, km=5, start=2000, end=2024, verified=False),
    "sg_lst_day":    dict(how="tesvis", src="MODIS Aqua", realm="land", product="MYD11A2", band="LST_Day_1km", lat=1.35, lon=103.8, km=5, start=2002, end=2024, verified=False,
                          note="8-day composites -> monthly mean in core; Aqua avoids Terra drift"),
    # --- atmosphere, by level (same process, opposite sign)
    "trop_t850":     dict(how="ea", src="MERRA-2", realm="atmosphere 850 hPa", short_name="M2IMNPASM", version="5.12.4", var="T", level=850, bbox=[-180, -60, 180, 60], start=1980, end=2024, verified=False),
    "strat_t5":      dict(how="ea", src="MERRA-2", realm="atmosphere 5 hPa", short_name="M2IMNPASM", version="5.12.4", var="T", level=5, bbox=[-180, -60, 180, 60], start=1980, end=2024, verified=False),
    "airs_t_check":  dict(how="ea", src="AIRS (AIRS-only V7)", realm="atmosphere levels", short_name="AIRS3STM", version="7.0", var="<list-vars>", bbox=[-180, -60, 180, 60], start=2002, end=2024, verified=False,
                          note="independent satellite check of the MERRA-2 levels"),
    # --- ocean
    "scs_sst":       dict(how="ea", src="MERRA-2 (SST boundary field)", realm="ocean", short_name="M2TMNXSLV", version="5.12.4", var="TS", bbox=SCS, start=1980, end=2024, verified=False,
                          note="surface skin temperature over open ocean; literature: +0.21 C/decade 1982-2022"),
    # --- water storage (observation vs model)
    "india_grace":   dict(how="ea", src="GRACE/GRACE-FO", realm="land water storage", short_name="TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4", version=None, var="lwe_thickness", bbox=N_INDIA, start=2002, end=2025, verified=False,
                          note="single file; leave mission gap empty"),
}


def run_catalog(names):
    for n in names or CATALOG:
        c = CATALOG[n]
        print(f"\n== {n}: {c['src']} [{c['realm']}] {c.get('note', '')}")
        if c["how"] == "power":
            power(SG[0], SG[1], c["params"], c["start"], c["end"])
        elif c["how"] == "tesvis":
            tesvis(c["lat"], c["lon"], c["product"], c["band"], c["start"], c["end"], c["km"])
        elif "<list-vars>" in c["var"]:
            print("   variable name unknown: run with --list-vars first, then fill it into CATALOG")
        else:
            earthaccess_monthly(c["short_name"], c["version"], c["var"], c["bbox"], c["start"], c["end"],
                                group=c.get("group"), level=c.get("level"), tag=n)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("power"); p.add_argument("--lat", type=float); p.add_argument("--lon", type=float)
    p.add_argument("--params", nargs="+"); p.add_argument("--start", type=int); p.add_argument("--end", type=int)
    t = sub.add_parser("tesvis"); t.add_argument("--lat", type=float); t.add_argument("--lon", type=float)
    t.add_argument("--product"); t.add_argument("--band"); t.add_argument("--start", type=int)
    t.add_argument("--end", type=int); t.add_argument("--km", type=int, default=0)
    e = sub.add_parser("earthaccess"); e.add_argument("--short-name"); e.add_argument("--version")
    e.add_argument("--var"); e.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    e.add_argument("--start", type=int); e.add_argument("--end", type=int)
    e.add_argument("--list-vars", action="store_true")
    e.add_argument("--group"); e.add_argument("--level", type=float); e.add_argument("--level-dim")
    c = sub.add_parser("catalog", help="pull named datasets from CATALOG (all if none given)")
    c.add_argument("names", nargs="*"); c.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.cmd == "catalog":
        if a.show:
            for n, v in CATALOG.items():
                print(f"{n:14s} {v['src']:28s} {v['realm']:22s} verified={v['verified']}")
        else:
            run_catalog(a.names)
        return
    if a.cmd == "power":
        power(a.lat, a.lon, a.params, a.start, a.end)
    elif a.cmd == "tesvis":
        tesvis(a.lat, a.lon, a.product, a.band, a.start, a.end, a.km)
    else:
        earthaccess_monthly(a.short_name, a.version, a.var, a.bbox or [-180, -90, 180, 90],
                            a.start, a.end, a.list_vars, a.group, a.level, a.level_dim)


if __name__ == "__main__":
    main()
