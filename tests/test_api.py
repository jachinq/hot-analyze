"""API 冒烟测试。"""

from fastapi.testclient import TestClient

from app.db.migrate import init_db
from app.main import app


def test_health():
    init_db()
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] is True


def test_stats_today_empty():
    init_db()
    client = TestClient(app)
    r = client.get("/api/stats/today")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "hot_count" in data
    assert "categories" in data
