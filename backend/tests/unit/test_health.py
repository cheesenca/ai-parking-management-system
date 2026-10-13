"""
Contoh unit test dasar. Tambahkan test asli sesuai domain masing-masing
fitur di dalam tests/unit/ (satu file per domain, mis. test_forecast.py).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
