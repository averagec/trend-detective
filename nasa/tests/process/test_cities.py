"""City list loader: the full CSV and the name-only list (coordinates from a second file)."""

from pathlib import Path

import pytest

from trend_detective.process.cities import COORDS, load_cities

ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_name_list_gets_coordinates_and_slug_ids(tmp_path):
    names = _write(
        tmp_path / "names.csv", "city,region\nBanda Aceh,Sumatra\nPangkal Pinang,Sumatra\n"
    )
    coords = _write(
        tmp_path / "coords.csv",
        "city,lat,lon\nBanda Aceh,5.55,95.32\nPangkal Pinang,-2.08,106.15\n",
    )
    cities = load_cities(names, coords)
    assert [c.city_id for c in cities] == ["banda_aceh", "pangkal_pinang"]
    assert (cities[0].lat, cities[0].lon) == (5.55, 95.32)
    assert cities[1].rainfall_source == "merra2:precip"


def test_name_without_coordinates_is_rejected(tmp_path):
    names = _write(tmp_path / "names.csv", "city,region\nAtlantis,Nowhere\n")
    coords = _write(tmp_path / "coords.csv", "city,lat,lon\nBanda Aceh,5.55,95.32\n")
    with pytest.raises(ValueError, match="no coordinates"):
        load_cities(names, coords)


def test_repo_city_list_loads_when_present():
    names = ROOT / "data" / "catalog" / "cities_idn.csv"
    if not names.exists():
        pytest.skip("the team's city list is not in this checkout")
    cities = load_cities(names, COORDS)
    assert len(cities) == 31
