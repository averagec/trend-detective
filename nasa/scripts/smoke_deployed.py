"""Smoke test for a running deployment: the API answers, and the main requests return data.

Uses only the standard library, so it runs anywhere. It reads only; nothing is written.

Examples:
    python scripts/smoke_deployed.py                       # the local server on 127.0.0.1:5000
    python scripts/smoke_deployed.py https://example.vercel.app
Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

DEFAULT = "http://127.0.0.1:5000"


def call(base: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    method = "POST" if body is not None else "GET"
    req = urllib.request.Request(
        base + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, {}


def main(argv: list[str]) -> int:
    base = (argv[0] if argv else DEFAULT).rstrip("/")
    checks = [
        ("healthz", "GET", "/healthz", None, lambda b: b.get("ok") is True),
        ("meta", "GET", "/api/meta", None, lambda b: len(b.get("variables", [])) > 0),
        ("regional map", "GET", "/api/map?variable=merra2:t2m", None,
         lambda b: len(b.get("regions", [])) == 3),
        ("trend", "GET", "/api/trend?variable=t2m&region=se_asia_maritime", None,
         lambda b: "statistics" in b),
        ("incidents (city)", "POST", "/api/incidents",
         {"mode": "city", "city_id": "jakarta", "hazard": "flood"},
         lambda b: len(b.get("counts", [])) == 39),
    ]
    failed = 0
    for name, _method, path, body, ok in checks:
        status, payload = call(base, path, body)
        passed = status == 200 and ok(payload)
        failed += not passed
        print(f"{'PASS' if passed else 'FAIL'}  {name:<18} HTTP {status}")
    # CIRCLE needs the cell cubes; a deployment without them answers with an error, reported here.
    status, _ = call(base, "/api/analyse", {"mode": "circle", "lat": -6.17, "lon": 106.83,
                                            "radius_km": 150, "variables": ["merra2:t2m"]})
    print(f"{'PASS' if status == 200 else 'NOTE'}  circle (cubes)      HTTP {status}")
    print(f"{len(checks) - failed} of {len(checks)} required checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
