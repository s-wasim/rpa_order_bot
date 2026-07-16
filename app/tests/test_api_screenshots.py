import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.screenshots import router as screenshots_router
from app import settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    shot_dir = tmp_path / "screenshots" / "7"
    shot_dir.mkdir(parents=True)
    (shot_dir / "001_search.png").write_bytes(b"\x89PNG\r\n\x1a\nfakepng")

    app_ = FastAPI()
    app_.include_router(screenshots_router)
    return TestClient(app_)


def test_get_existing_screenshot(client):
    resp = client.get("/api/screenshots/7/001_search.png")
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG\r\n\x1a\nfakepng"
    assert resp.headers["content-type"] == "image/png"


def test_get_missing_screenshot_404(client):
    resp = client.get("/api/screenshots/7/999_missing.png")
    assert resp.status_code == 404


def test_path_traversal_rejected(client):
    resp = client.get("/api/screenshots/7/..%2F..%2Fetc%2Fpasswd.png")
    assert resp.status_code in (400, 404)
