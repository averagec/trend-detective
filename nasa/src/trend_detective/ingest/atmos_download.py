"""Download NASA atmosphere and land data by topic group, from NASA Earthdata.

Owns: topic presets only. Search, login and download live in ocean_download.py (shared).
Temperature comes first. Composition and land groups follow.

Groups (keywords are searched in CMR; see the dry run for what matches):
    temperature  atmospheric temperature, air temperature
    composition  ozone, nitrogen dioxide, carbon monoxide, carbon dioxide, aerosol optical depth
    land         land surface temperature, vegetation index, soil moisture

Examples (Asia-Pacific box, 1992-2022):
    python src/trend_detective/ingest/atmos_download.py --group temperature --dry-run
    python src/trend_detective/ingest/atmos_download.py --group temperature
    python src/trend_detective/ingest/atmos_download.py --group composition --dry-run
    python src/trend_detective/ingest/atmos_download.py --group land --dry-run

Writes data/raw/<group>/<short_name>/ (git-ignored), with manifest.csv and provenance.json.
Needs EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env for real downloads (not for --dry-run).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from trend_detective.ingest.ocean_download import ASIA_PACIFIC, cmd_download  # noqa: E402

GROUPS: dict[str, list[str]] = {
    "temperature": ["atmospheric temperature", "air temperature"],
    "composition": [
        "ozone",
        "nitrogen dioxide",
        "carbon monoxide",
        "carbon dioxide",
        "aerosol optical depth",
    ],
    "land": ["land surface temperature", "vegetation index", "soil moisture"],
}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--group", action="append", choices=sorted(GROUPS), default=None,
                   help="repeatable; default: temperature")
    p.add_argument("--start", type=int, default=1992)
    p.add_argument("--end", type=int, default=2022)
    p.add_argument("--bbox", default=ASIA_PACIFIC, help="west,south,east,north")
    p.add_argument("--limit", type=int, default=20, help="max collections per keyword")
    p.add_argument("--max-granules", type=int, default=400)
    p.add_argument("--include-large", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    for group in args.group or ["temperature"]:
        print(f"== {group} ==")
        run = argparse.Namespace(
            keyword=GROUPS[group],
            concept_id=[],
            start=args.start,
            end=args.end,
            bbox=args.bbox,
            limit=args.limit,
            max_granules=args.max_granules,
            include_large=args.include_large,
            dry_run=args.dry_run,
        )
        cmd_download(run, out_root=ROOT / "data" / "raw" / group)


if __name__ == "__main__":
    main()
