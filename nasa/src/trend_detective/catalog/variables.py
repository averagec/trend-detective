"""Variables the app offers: plain-language labels, the question each answers, and what it means.

Owns: text only. No numbers and no statistics (those come from core/). See docs/product-sense.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Variable:
    key: str  # short name used in the processed CSV
    label: str
    question: str  # the question a student or member of the public asks
    description: str  # what the number is, in plain language


VARIABLES: dict[str, Variable] = {
    v.key: v
    for v in [
        Variable(
            "t2m",
            "Mean 2 m air temperature",
            "Is it getting hotter?",
            "Air temperature 2 metres above the ground, averaged over each month.",
        ),
        Variable(
            "t2mmax",
            "Average daily maximum 2 m air temperature",
            "Are the hottest days getting hotter?",
            "The hottest temperature reached each day, averaged over each month.",
        ),
        Variable(
            "precip",
            "Precipitation",
            "Is it raining more or less?",
            "Rain and other precipitation reaching the ground, in mm per day (monthly mean).",
        ),
        Variable(
            "qv2m",
            "2 m specific humidity",
            "Is the air getting more humid?",
            "How much water vapour the air holds, in grams per kilogram of air.",
        ),
        Variable(
            "vpd",
            "Vapour pressure deficit",
            "Is the air getting drier, so plants lose more water?",
            "How far the air is from being saturated with water vapour. Higher values dry plants "
            "and soils faster.",
        ),
        Variable(
            "evap",
            "Surface evaporation",
            "Is more water evaporating from the surface?",
            "Water that leaves the surface by evaporation, in mm per day (monthly mean).",
        ),
        Variable(
            "tsurf",
            "Land surface temperature",
            "Is the land surface getting hotter?",
            "Temperature of the land surface itself, including snow, averaged over each month.",
        ),
        Variable(
            "ps",
            "Surface pressure",
            "Is the air pressure at the surface changing?",
            "Air pressure at the surface of the Earth, averaged over each month.",
        ),
    ]
}
