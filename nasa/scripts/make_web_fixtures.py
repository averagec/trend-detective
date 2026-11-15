"""Write real API responses (a small synthetic record) as fixtures for the website's tests.

The Flask app computes everything, so the fixtures are exactly what the page receives. Run this
after an intended API change, then `npm test` in web/ and `pytest tests/app` (the shape test).

    python scripts/make_web_fixtures.py
"""

import csv
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_detective.app.web import create_app  # noqa: E402

OUT = ROOT / "web" / "tests" / "fixtures"
# region, variable, unit, slope per month, seed (2000-01 to 2007-12)
SERIES = [
    ("east_asia_land", "t2m", "K", 0.0030, 1),
    ("se_asia_maritime", "t2m", "K", -0.0020, 3),
    ("north_asia_siberia", "t2m", "K", 0.0, 5),
    ("east_asia_land", "precip", "mm day-1", 0.0, 2),
    ("se_asia_maritime", "precip", "mm day-1", 0.0, 4),
]


def main() -> None:
    rows = []
    for region, variable, unit, slope, seed in SERIES:
        rng = np.random.default_rng(seed)
        for i in range(12 * 8):
            v = 280 + 3 * math.sin(2 * math.pi * i / 12) + slope * i + rng.normal(0, 0.3)
            rows.append(
                {
                    "region": region,
                    "variable": variable,
                    "period": f"{2000 + i // 12}-{i % 12 + 1:02d}",
                    "value": f"{v:.5g}",
                    "unit": unit,
                    "n_cells": 1,
                    "n_valid": 1,
                    "n_days": "",
                }
            )
    csv_path = Path(tempfile.mkdtemp()) / "monthly_regional.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    client = create_app(csv_path).test_client()
    values = [
        round(280 + 3 * math.sin(2 * math.pi * ((2 + i) % 12) / 12) + 0.0025 * i, 3)
        for i in range(48)
    ]
    values[10] = None
    calls = {
        "trend": client.get("/api/trend?variable=t2m&region=east_asia_land"),
        "scan": client.get("/api/scan?variable=t2m"),
        "analyse": client.post(
            "/api/analyse-series",
            json={"label": "Station", "unit": "K", "start": "2000-03", "values": values},
        ),
        "trend_short": client.get(
            "/api/trend?variable=t2m&region=east_asia_land&from=2000&to=2000"
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, response in calls.items():
        assert response.status_code == 200, (name, response.status_code, response.get_data())
        text = json.dumps(response.get_json(), indent=1)
        (OUT / f"{name}.json").write_text(text, encoding="utf-8")
    print(f"wrote {len(calls)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
