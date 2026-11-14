# Tech debt tracker

Hackathon shortcuts are fine; untracked ones aren't.

| Item | Where | Why we took it | Priority (P0–P2) |
|---|---|---|---|
| | | | |

- Shoreline: tide level at acquisition is not corrected (waterline moves with tide). Use PSMSL Singapore gauge or restrict to seawalled sites; state the limitation in results.
- Shoreline: ingest only lists scenes + browse; reading real GRD backscatter (GeoTIFF -> dB array) is not built yet.
- sites.py bboxes are approximate: verify in Worldview/Vertex.
- raw_to_json: ECCO LLC90 native-grid regional mean sits ~8 mm above the 0.5° product (different valid-cell masks). Find out why before showing LLC90 numbers.
- raw_to_json: ECCO LLC90 V4R4B is skipped until its manifest.csv exists; rerun `python scripts/raw_to_json.py` after the download finishes.
