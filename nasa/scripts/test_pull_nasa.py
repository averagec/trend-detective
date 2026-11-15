import json
import sys
import types

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, "/home/claude/hackathon/ingest_kit")
import pull_nasa as pn


class R:
    def __init__(s, j, url="u"): s._j, s.url = j, url
    def json(s): return s._j
    def raise_for_status(s): pass

# --- POWER: real Singapore values reshaped into POWER's JSON (incl. YYYY13 keys + a fill)
d = json.load(open("/home/claude/hackathon/protocol_demo/power_singapore_1981_2024.json"))
t2m = {}
for i, v in enumerate(d["T2M"]):
    y, m = 1981 + i // 12, i % 12 + 1
    t2m[f"{y}{m:02d}"] = v
    if m == 12: t2m[f"{y}13"] = 99.9
t2m["198101"] = -999
pn.requests.get = lambda *a, **k: R({"header": {"fill_value": -999},
    "properties": {"parameter": {"T2M": t2m}}, "parameters": {"T2M": {"units": "C"}}})
pn.power(1.35, 103.9, ["T2M"], 1981, 2024)
rows = pd.read_csv("data/raw/power/T2M_1.35_103.9_1981_2024.csv")
assert len(rows) == 527 and rows.value.max() < 40, rows.describe()   # 528 - 1 fill, no 13-keys
print("POWER ok", len(rows))

# --- TESViS: 23 dates -> 3 chunks of <=10; scale; fill dropped
dates = [{"calendar_date": f"2000-{(i//2)+1:02d}-{1+15*(i%2):02d}", "modis_date": f"A2000{i:03d}"} for i in range(23)]
calls = []
def fake(url, params=None, headers=None, timeout=None):
    calls.append(url)
    if url.endswith("/dates"): return R({"dates": dates})
    s = [x for x in dates if params["startDate"] <= x["modis_date"] <= params["endDate"]]
    return R({"scale": "0.0001", "subset": [{"calendar_date": x["calendar_date"], "data": [5000, 7000, -3000]} for x in s]})
pn.requests.get = fake; pn.time.sleep = lambda s: None
pn.tesvis(1.35, 103.8, "MOD13Q1", "250m_16_days_NDVI", 2000, 2000)
tv = pd.read_csv("data/raw/tesvis/MOD13Q1_250m_16_days_NDVI_1.35_103.8_km0_2000_2000.csv")
assert len(tv) == 23 and abs(tv.value.iloc[0] - 0.6) < 1e-9 and sum(c.endswith("subset") for c in calls) == 3
print("TESViS ok", len(tv), "rows,", sum(c.endswith('subset') for c in calls), "subset calls")

# --- earthaccess: fake granules; field = 10 + lat so the cos-lat weighted mean is checkable
lat = np.arange(-89.75, 90, 0.5); lon = np.arange(0.25, 360, 0.5)
def gran(month):
    v = (10 + lat)[None, :, None] * np.ones((1, lat.size, lon.size))
    return xr.Dataset({"precip": (("time", "lat", "lon"), v)},
                      coords={"time": [pd.Timestamp(f"2000-{month:02d}-01")], "lat": lat, "lon": lon})
fake_ea = types.SimpleNamespace(login=lambda: None,
    search_data=lambda **k: [1, 2], open=lambda res: [gran(1), gran(2)])
sys.modules["earthaccess"] = fake_ea
real_open = xr.open_dataset; xr.open_dataset = lambda f, **k: f
pn.earthaccess_monthly("GPCPMON", "3.3", "precip", [100, -1, 106, 4], 2000, 2000)
xr.open_dataset = real_open
ea = pd.read_csv("data/raw/earthaccess/GPCPMON_3.3_precip_100_-1_106_4_2000_2000.csv")
la = lat[(lat >= -1) & (lat <= 4)]; expect = np.average(10 + la, weights=np.cos(np.deg2rad(la)))
assert len(ea) == 2 and abs(ea.value[0] - expect) < 1e-9, (ea, expect)
print("earthaccess ok", ea.value.tolist(), "expected", round(expect, 4))

# --- earthaccess on a -180..180 grid with descending lat (other common layout)
lon2 = np.arange(-179.75, 180, 0.5); lat2 = lat[::-1]
g = xr.Dataset({"precip": (("time", "lat", "lon"), (10 + lat2)[None, :, None] * np.ones((1, lat2.size, lon2.size)))},
               coords={"time": [pd.Timestamp("2000-03-01")], "lat": lat2, "lon": lon2})
fake_ea.open = lambda res: [g]; xr.open_dataset = lambda f, **k: f
pn.earthaccess_monthly("GPCPMON", "3.3", "precip", [100, -1, 106, 4], 2000, 2000)
xr.open_dataset = real_open
ea2 = pd.read_csv("data/raw/earthaccess/GPCPMON_3.3_precip_100_-1_106_4_2000_2000.csv")
assert abs(ea2.value[0] - expect) < 1e-9
print("earthaccess descending-lat ok")

# --- pressure levels: pick 850 vs 5 hPa from a 3-D field (T = level value + lat term)
lev = np.array([1000., 850., 500., 5., 1.])
g3 = xr.Dataset({"T": (("time", "lev", "lat", "lon"),
                 (lev[None, :, None, None] + 0 * lat[None, None, :, None]) * np.ones((1, lev.size, lat.size, lon.size)))},
                coords={"time": [pd.Timestamp("2000-01-01")], "lev": lev, "lat": lat, "lon": lon})
fake_ea.open = lambda res: [g3]; xr.open_dataset = lambda f, **k: f
pn.earthaccess_monthly("M2IMNPASM", "5.12.4", "T", [-180, -60, 180, 60], 2000, 2000, level=850, tag="t850")
pn.earthaccess_monthly("M2IMNPASM", "5.12.4", "T", [-180, -60, 180, 60], 2000, 2000, level=5, tag="t5")
xr.open_dataset = real_open
assert abs(pd.read_csv("data/raw/earthaccess/t850.csv").value[0] - 850) < 1e-6 and abs(pd.read_csv("data/raw/earthaccess/t5.csv").value[0] - 5) < 1e-6
print("pressure-level selection ok")

# --- catalog: every entry names an instrument/model from the brief and a realm
named = ("MODIS", "AIRS", "GPM", "MERRA-2", "GLDAS")
covered = {k for k in named if any(k in v["src"] for v in pn.CATALOG.values())}
assert covered == set(named), set(named) - covered
realms = " ".join(v["realm"] for v in pn.CATALOG.values())
assert all(r in realms for r in ("land", "ocean", "atmosphere"))
print("catalog covers", sorted(covered), "and land/ocean/atmosphere")
