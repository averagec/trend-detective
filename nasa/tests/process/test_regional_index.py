"""Climate indices in the regional map: one global series, reported like a region."""

from trend_detective.process import regional_map


def test_index_layer_is_one_global_series(tmp_path, monkeypatch):
    # 10 years of a rising index, monthly, keyed YYYYMM as indicator_monthly returns it.
    monthly = {f"{1990 + m // 12}{m % 12 + 1:02d}": 0.01 * m for m in range(120)}
    monkeypatch.setattr(regional_map, "indicator_monthly", lambda name: monthly)
    payload = regional_map.build_map(tmp_path, "index:enso")
    assert [r["key"] for r in payload["regions"]] == ["global"]
    region = payload["regions"][0]
    assert region["name"] == "Global"
    assert region["status"] == "ok"
    # The project window starts in 1980, so the timeline starts there; the ten years are in it.
    assert region["first_period"] == "1980-01"
    assert region["last_period"] == "1999-12"
    assert region["n_points"] == 120
    assert region["slope_per_decade"] > 0


def test_index_with_no_file_gives_no_regions(tmp_path, monkeypatch):
    monkeypatch.setattr(regional_map, "indicator_monthly", lambda name: {})
    payload = regional_map.build_map(tmp_path, "index:pdo")
    assert payload["regions"] == []
