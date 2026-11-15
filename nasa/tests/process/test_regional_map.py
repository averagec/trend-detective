"""A box with no valid values is reported as no_data, not as a trend with empty numbers."""

import json

from trend_detective.process.regional_map import build_map


def test_box_without_values_is_no_data(tmp_path):
    lines = ["region,variable,period,value,unit,n_cells,n_valid,n_days"]
    for year in range(1990, 2000):
        for month in range(1, 13):
            p = f"{year}-{month:02d}"
            lines.append(f"east_asia_land,t2m,{p},{250 + 0.01 * (year - 1990)},K,10,10,")
            lines.append(f"se_asia_maritime,t2m,{p},,K,10,0,")  # no valid values in this box
    path = tmp_path / "merra2" / "monthly_regional.csv"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = build_map(tmp_path, "merra2:t2m")
    regions = {r["key"]: r for r in payload["regions"]}
    assert regions["se_asia_maritime"]["status"] == "no_data"
    assert regions["east_asia_land"]["status"] == "ok"
    assert regions["east_asia_land"]["direction"] in ("rise", "fall", "none", "unclear")
    json.dumps(payload)  # no NaN left in the payload
