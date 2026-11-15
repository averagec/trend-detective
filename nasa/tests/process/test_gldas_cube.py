"""The GLDAS soil-moisture cube: one month, a small synthetic file, fill values masked."""

import h5py
import numpy as np

from trend_detective.process.cell_cube import build_gldas


def test_gldas_cube_masks_fill_and_keeps_the_grid(tmp_path):
    folder = tmp_path / "gldas" / "2000"
    folder.mkdir(parents=True)
    lat = np.array([-1.0, -0.75, -0.5, -0.25])
    lon = np.array([100.0, 100.25, 100.5, 100.75])
    sm = np.full((1, 4, 4), 20.0)
    sm[0, 0, 0] = -9999.0  # fill value in one cell
    with h5py.File(folder / "x.A200001.021.nc4", "w") as f:
        f["lat"] = lat
        f["lon"] = lon
        f["SoilMoi0_10cm_inst"] = sm
    cube = build_gldas(folder=tmp_path / "gldas")
    arr = cube.values["gldas_sm_0_10cm"]
    assert arr.shape == (1, 4, 4)
    assert cube.periods["gldas_sm_0_10cm"] == ["200001"]
    assert np.isnan(arr[0, 0, 0])
    assert arr[0, 1, 1] == 20.0
    assert cube.manifest["units"]["gldas_sm_0_10cm"] == "kg m-2"
