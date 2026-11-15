"""Tests for the /ocean page and the images it shows: served from disk, offline, and safe."""

from pathlib import Path

import pytest

from trend_detective.app.web import create_app

PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"not a real picture, but served as one"


@pytest.fixture
def images(tmp_path: Path) -> Path:
    folder = tmp_path / "images"
    folder.mkdir()
    (folder / "ocean_ssh_mean.png").write_bytes(PNG_HEADER)
    (folder / "sar_browse_scenes.png").write_bytes(PNG_HEADER)
    return folder


@pytest.fixture
def client(tmp_path: Path, images: Path):
    # The trend CSV is not needed for the ocean page, so point at a file that does not exist.
    return create_app(tmp_path / "missing.csv", images_dir=images).test_client()


def test_the_ocean_page_shows_both_pictures(client):
    html = client.get("/ocean").get_data(as_text=True)
    assert 'src="/demo/ocean_ssh_mean.png"' in html
    assert 'src="/demo/sar_browse_scenes.png"' in html
    assert "not rendered yet" not in html


def test_pictures_are_served_as_png(client):
    response = client.get("/demo/ocean_ssh_mean.png")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data == PNG_HEADER


def test_a_missing_picture_is_a_clear_message_not_a_crash(tmp_path: Path):
    client = create_app(tmp_path / "missing.csv", images_dir=tmp_path / "none").test_client()
    html = client.get("/ocean").get_data(as_text=True)
    assert client.get("/ocean").status_code == 200
    assert "not rendered yet" in html
    assert client.get("/demo/ocean_ssh_mean.png").status_code == 404


def test_the_picture_route_cannot_leave_the_images_folder(client):
    assert client.get("/demo/..%2Fweb.py").status_code == 404
    assert client.get("/demo/%2e%2e/%2e%2e/secret.txt").status_code == 404
