"""Coastal-change study sites (Asia-Pacific). Owns: site definitions only, no I/O.

bbox = west,south,east,north in degrees. NOTE: bboxes are approximate starting points;
verify each one in NASA Worldview / ASF Vertex before trusting it, and tighten the crop so
the shoreline crosses the whole crop (see core/shoreline.py).
sea_side = which edge of the crop the open sea is on.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    key: str
    name: str
    bbox: str
    sea_side: str  # "east" | "west" | "north" | "south"
    why: str


SITES: dict[str, Site] = {
    "singapore_east": Site(
        "singapore_east", "Singapore east coast (reclamation)", "103.95,1.28,104.10,1.40", "east",
        "Land reclamation: expect seaward growth (positive trend)."),
    "mekong_camau": Site(
        "mekong_camau", "Mekong Delta, Ca Mau coast (Vietnam)", "104.70,8.55,105.00,8.85", "west",
        "Documented mangrove-coast erosion: expect retreat (negative trend)."),
    "jakarta_north": Site(
        "jakarta_north", "North Jakarta coast (Indonesia)", "106.70,-6.15,106.95,-6.00", "north",
        "Subsidence + reclamation: mixed signals, a good opposite-trend comparison."),
}
