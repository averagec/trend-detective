import json, sys, pathlib
import numpy as np, xarray as xr
ROOT = pathlib.Path(__file__).resolve().parents[2]
TOO_SMALL = {'Singapore', 'Brunei', 'Timor-Leste'}
pts = json.load(open(ROOT / 'scripts/data/sample_points.json'))
out_p = ROOT / 'public/data/sea_data.json'
out = json.load(open(out_p)) if out_p.exists() else {'meta': {}}
ds = xr.open_dataset(sys.argv[1])
lwe = ds['lwe_thickness']
times = ds['time'].values.astype('datetime64[M]')
y0 = int(str(times.min())[:4])
y1 = int(str(times.max())[:4])
n = (y1 - y0 + 1) * 12
lats, lons = (ds['lat'].values, ds['lon'].values)
out['tws'] = {}
for name, p in pts.items():
    if name in TOO_SMALL:
        continue
    ii = [int(np.abs(lats - la).argmin()) for lo, la in p['grace']]
    jj = [int(np.abs(lons - lo % 360).argmin()) for lo, la in p['grace']]
    cells = sorted(set(zip(ii, jj)))
    series = lwe.values[:, [c[0] for c in cells], [c[1] for c in cells]].mean(axis=1)
    m = [None] * n
    for t, v in zip(times, series):
        y, mo = (int(str(t)[:4]), int(str(t)[5:7]))
        if np.isfinite(v):
            m[(y - y0) * 12 + mo - 1] = round(float(v), 3)
    out['tws'][name] = {'y0': y0, 'm': m}
    print(f'{name:12s} {len(cells):3d} cells, {sum((x is not None for x in m))} months')
out['meta']['tws_source'] = 'JPL GRACE/GRACE-FO mascon RL06.3 CRI'
json.dump(out, open(out_p, 'w'))
print('updated', out_p)
