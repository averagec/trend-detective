"""Tests for scripts/build_processed.py. No raw data and no network: they use a tiny CSV."""

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from trend_detective.app.web import create_app
from trend_detective.process import merra2_clean

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "build_processed", ROOT / "scripts/build_processed.py"
)
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)


def make_rows(pairs, years=15):
    rng = np.random.default_rng(3)
    rows = []
    for region, variable in pairs:
        for i in range(12 * years):
            value = 290 + 3 * math.sin(2 * math.pi * i / 12) + 0.002 * i + rng.normal(0, 0.2)
            rows.append(
                {
                    "region": region,
                    "variable": variable,
                    "period": f"{2000 + i // 12}-{i % 12 + 1:02d}",
                    "value": value,
                    "unit": "K",
                    "n_cells": "100",
                    "n_valid": "100",
                    "n_days": "",
                }
            )
    return rows


@pytest.fixture
def data_dir(tmp_path):
    rows = make_rows(
        [("east_asia_land", "t2m"), ("se_asia_maritime", "t2m"), ("east_asia_land", "ps")]
    )
    bp.write_rows(rows, tmp_path / "processed" / "merra2" / "monthly_regional.csv")
    return tmp_path


def test_merge_replaces_only_the_requested_series():
    old = make_rows([("east_asia_land", "t2m"), ("east_asia_land", "ps")], years=2)
    new = make_rows([("east_asia_land", "t2m"), ("se_asia_maritime", "t2m")], years=3)
    merged = bp.merge_rows(old, new, "east_asia_land", "t2m")
    count = lambda r, v: sum(x["region"] == r and x["variable"] == v for x in merged)  # noqa: E731
    assert count("east_asia_land", "t2m") == 36  # replaced by the new 3 years
    assert count("east_asia_land", "ps") == 24  # untouched
    assert count("se_asia_maritime", "t2m") == 0  # other regions in `new` are not pulled in


def test_rewriting_the_committed_csv_changes_nothing(tmp_path):
    path = ROOT / "data" / "processed" / "merra2" / "monthly_regional.csv"
    if not path.exists():
        pytest.skip("processed CSV not present")
    rewritten = tmp_path / "monthly_regional.csv"
    bp.write_rows(bp.read_rows(path), rewritten)
    # Line endings may differ on Windows (the committed file is CRLF); compare the content.
    norm = lambda b: b.replace(b"\r\n", b"\n")  # noqa: E731
    assert norm(rewritten.read_bytes()) == norm(path.read_bytes())


def test_demo_step_makes_an_offline_folder_the_app_can_serve(data_dir):
    csv_path = data_dir / "processed" / "merra2" / "monthly_regional.csv"
    cases = [("east_asia_land", "t2m"), ("se_asia_maritime", "t2m"), ("north_asia_siberia", "t2m")]
    demo = data_dir / "demo"
    copied = bp.step_demo(csv_path, demo, cases)
    assert copied == cases[:2]  # the case with no data is skipped, not invented
    manifest = json.loads((demo / "cases.json").read_text(encoding="utf-8"))
    assert [c["region"] for c in manifest["cases"]] == ["east_asia_land", "se_asia_maritime"]
    assert (demo / "json" / "east_asia_land" / "t2m.json").exists()
    assert not (demo / "json" / "east_asia_land" / "ps.json").exists()  # not a demo case
    client = create_app(demo / "monthly_regional.csv").test_client()
    data = client.get("/api/trend?variable=t2m&region=east_asia_land").get_json()
    assert data["band"] and data["statistics"]["ols_per_decade"] > 0


def test_dry_run_writes_nothing_and_says_clean_is_blocked_without_raw(
    data_dir, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(merra2_clean, "SUBSET", tmp_path / "no_raw")
    before = sorted(p.relative_to(data_dir) for p in data_dir.rglob("*"))
    code = bp.main(
        [
            "--region",
            "east_asia_land",
            "--variable",
            "t2m",
            "--dry-run",
            "--data-dir",
            str(data_dir),
        ]
    )
    assert code == 1
    assert "BLOCKED" in capsys.readouterr().out
    assert sorted(p.relative_to(data_dir) for p in data_dir.rglob("*")) == before


def test_dry_run_of_the_export_steps_passes(data_dir, capsys):
    code = bp.main(
        [
            "--region", "east_asia_land", "--variable", "t2m",
            "--steps", "analyse", "demo",
            "--demo", "east_asia_land:t2m",
            "--dry-run", "--data-dir", str(data_dir),
        ]
    )  # fmt: skip
    assert code == 0
    assert "app can read it" in capsys.readouterr().out


def test_contract_check_catches_a_csv_the_app_cannot_read(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("region,variable,period\neast_asia_land,t2m,2000-01\n", encoding="utf-8")
    assert "missing columns" in bp.check_app_contract(bad, [])[0]
    unknown = tmp_path / "unknown.csv"
    bp.write_rows(make_rows([("mars", "t2m")], years=1), unknown)
    problems = bp.check_app_contract(unknown, [("east_asia_land", "t2m")])
    assert any("unknown region" in p for p in problems)
    assert any("no rows for east_asia_land" in p for p in problems)


def test_a_real_run_without_raw_files_refuses_to_download(data_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(merra2_clean, "SUBSET", tmp_path / "no_raw")
    code = bp.main(["--region", "east_asia_land", "--variable", "t2m", "--data-dir", str(data_dir)])
    assert code == 1
    assert "--confirm-download" in capsys.readouterr().out
