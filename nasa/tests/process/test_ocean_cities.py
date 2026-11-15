import numpy as np

from trend_detective.process import ocean_cities as oc


def city(lat, lon, coast_km=5.0):
    return oc.City("Test", "Prov", lat, lon, 1, False, coast_km)


def test_nearest_cells_skip_land_and_far_cells():
    lats = np.array([-1.0, -0.5, 0.0, 0.5])
    lons = np.array([100.0, 100.5, 101.0, 101.5])
    ocean = np.ones((4, 4), bool)
    ocean[2, 1] = False
    cells = oc.nearest_cells(city(0.0, 100.5), lats, lons, ocean)
    assert len(cells) == oc.MAX_CELLS
    assert (2, 1) not in [(i, j) for i, j, _ in cells]
    assert all(d <= oc.MAX_KM for *_, d in cells)
    assert [d for *_, d in cells] == sorted(d for *_, d in cells)


def test_city_series_is_millimetres_and_keeps_gaps():
    lats = np.array([0.0, 0.5])
    ssh = np.zeros((3, 2, 1))
    ssh[0] = 0.1
    ssh[1] = np.nan
    ssh[2, 0, 0], ssh[2, 1, 0] = 0.2, 0.4
    s = oc.city_series(city(0, 0), lats, ssh, [(0, 0, 1.0), (1, 0, 2.0)])
    assert s[0] == 100.0
    assert np.isnan(s[1])
    assert 200.0 < s[2] < 400.0


def test_inland_cities_are_not_coastal():
    assert not city(0, 0, coast_km=oc.COAST_KM + 1).coastal
    assert city(0, 0, coast_km=oc.COAST_KM).coastal
