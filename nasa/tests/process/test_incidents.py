"""GDIS incident counts: placement on cells, the window, the circle totals (synthetic data)."""

import numpy as np

from trend_detective.process.gdis import count_events
from trend_detective.process.incidents import circle, city


def _grid():
    lat = np.arange(-2.0, 2.01, 0.5)
    lon = np.arange(104.0, 108.01, 0.5)
    return lat, lon


def test_events_are_placed_on_the_nearest_cell_inside_the_window():
    lat, lon = _grid()
    def rec(year, hazard, la, lo):
        return {"year": year, "hazard": hazard, "latitude": la, "longitude": lo}

    events = [
        rec(1985, "flood", -0.1, 106.1),  # placed
        rec(1985, "flood", -0.1, 106.1),  # placed (same cell, same year)
        rec(1979, "flood", -0.1, 106.1),  # before the window: dropped
        rec(2019, "flood", -0.1, 106.1),  # after the window: dropped
        rec(1985, "storm", -0.1, 106.1),  # not a flood or drought: dropped
        rec(1985, "drought", 40.0, 10.0),  # outside the box: dropped
    ]
    years, counts, stats = count_events(events, lat, lon)
    assert counts["flood"].sum() == 2
    assert counts["drought"].sum() == 0
    assert stats["outside_box"] == 1
    assert years[0] == 1980 and years[-1] == 2018


def test_city_and_circle_use_the_same_counts():
    lat, lon = _grid()
    years = np.arange(1980, 2019)
    rng = np.random.default_rng(4)
    data = {"lat": lat, "lon": lon, "years": years,
            "flood": rng.poisson(0.5, (years.size, lat.size, lon.size)),
            "drought": np.zeros((years.size, lat.size, lon.size), dtype=int)}
    one = city(data, "flood", -0.1, 106.1)
    assert len(one["counts"]) == years.size
    big = circle(data, "flood", -0.5, 106.0, 250.0)
    assert sum(big["combined"]["counts"]) == sum(r["total"] for r in big["cells"])
    a = big["agreement"]
    assert a["rising"] + a["falling"] + a["not_significant"] == big["cells_in_circle"]
