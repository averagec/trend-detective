"""Export the regional trend numbers for the three boxes as one static JSON file for the web page.

Every number comes from core/ through process/regional_map.build_map (the same function that
/api/map uses): core.summary.summarise for each box, and Benjamini-Hochberg across the boxes for
each test. This script only reads the processed CSVs and writes JSON. It does not ingest data.

Inputs : data/processed/merra2/monthly_regional.csv, data/processed/witness/witness_regional.csv,
         data/processed/ocean/ocean_regional.csv
Output : web/public/data/regional_data.json  (default; change with --out)

Examples:
    python scripts/export_regional.py
    python scripts/export_regional.py --out some/other/regional_data.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # lets the script run without `pip install -e .`

from trend_detective.process.regional_map import LAYERS, build_map  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "web" / "public" / "data" / "regional_data.json"


def export(processed_dir: Path = PROCESSED) -> dict:
    layers: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    for key in LAYERS:
        try:
            layers[key] = build_map(processed_dir, key, freq="monthly", include_series=True)
        except FileNotFoundError as err:
            skipped[key] = str(err)
    return {
        "note": (
            "Made by scripts/export_regional.py from process/regional_map.build_map "
            "(core statistics). Do not edit."
        ),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "freq": "monthly",
        "layers": layers,
        "skipped": skipped,
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)
    payload = export()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['layers'])} layers to {args.out}")
    for key, why in payload["skipped"].items():
        print(f"skipped {key}: {why}")


if __name__ == "__main__":
    main()
