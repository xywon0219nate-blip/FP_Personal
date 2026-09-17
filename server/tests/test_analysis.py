from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_analysis_missing_fields_returns_422():
    res = client.post("/api/analysis", json={})
    assert res.status_code == 422


def test_analysis_unknown_region_returns_404_or_error():
    res = client.post("/api/analysis", json={
        "region": "존재안하는지역",
        "majorCategory": "테스트업종",
        "minorCategory": "테스트업종",
        "targetSales": 1000,
    })
    assert res.status_code in (404, 422)