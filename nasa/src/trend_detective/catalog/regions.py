"""Regions for the MERRA-2 pipeline. Owns: region definitions only, no I/O.

bbox = west,south,east,north in degrees. A MERRA-2 cell is 0.625 x 0.5 degrees, so a region
should cover several cells (roughly 4 x 4 or more). Smaller areas (e.g. the coastal sites in
catalog/sites.py) are below the grid and must not be analysed with MERRA-2.

PROPOSED: these three boxes are a starting point for the team to confirm, not final choices.
They are chosen to contrast land and ocean and to give a chance of opposite trends.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    key: str
    name: str
    bbox: tuple[float, float, float, float]  # west, south, east, north
    why: str


REGIONS: dict[str, Region] = {
    "se_asia_maritime": Region(
        "se_asia_maritime",
        "Maritime Southeast Asia (Indonesia, Malaysia, Philippines)",
        (95.0, -10.0, 141.0, 10.0),
        "Mostly ocean with many islands; sensitive to ENSO and sea-surface warming.",
    ),
    "east_asia_land": Region(
        "east_asia_land",
        "Eastern China and Korea",
        (110.0, 25.0, 130.0, 42.0),
        "Dense population; large changes in rainfall and heat; land-dominated.",
    ),
    "north_asia_siberia": Region(
        "north_asia_siberia",
        "Southern Siberia and Mongolia",
        (80.0, 45.0, 120.0, 60.0),
        "Fast warming at high latitude; land surface temperature and evaporation respond strongly.",
    ),
}
