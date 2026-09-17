from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_get_recent_selections_without_token_returns_401():
    res = client.get("/api/recent-selections", params={"feature_key": "ai-analysis"})
    assert res.status_code == 401


def test_create_list_and_delete_recent_selection(signup_and_login):
    headers = signup_and_login("recent-user1@example.com")

    create_res = client.post(
        "/api/recent-selections",
        headers=headers,
        json={
            "feature_key": "ai-analysis",
            "label": "강남구 · 한식음식점",
            "payload": {"region": "11680"},
        },
    )
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["label"] == "강남구 · 한식음식점"
    assert created["payload"] == {"region": "11680"}

    list_res = client.get(
        "/api/recent-selections", headers=headers, params={"feature_key": "ai-analysis"}
    )
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]

    delete_res = client.delete(
        f"/api/recent-selections/{created['id']}", headers=headers
    )
    assert delete_res.status_code == 200

    list_after_delete = client.get(
        "/api/recent-selections", headers=headers, params={"feature_key": "ai-analysis"}
    )
    assert list_after_delete.json() == []


def test_recreating_same_label_replaces_the_old_entry(signup_and_login):
    """같은 feature_key + label로 다시 등록하면, 기존 항목을 지우고 새로 추가한다."""
    headers = signup_and_login("recent-user2@example.com")

    for payload in ({"region": "old"}, {"region": "new"}):
        res = client.post(
            "/api/recent-selections",
            headers=headers,
            json={"feature_key": "ai-analysis", "label": "같은 라벨", "payload": payload},
        )
        assert res.status_code == 200

    list_res = client.get(
        "/api/recent-selections", headers=headers, params={"feature_key": "ai-analysis"}
    )
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["payload"] == {"region": "new"}


def test_only_latest_three_selections_are_kept(signup_and_login):
    headers = signup_and_login("recent-user3@example.com")

    for i in range(4):
        res = client.post(
            "/api/recent-selections",
            headers=headers,
            json={"feature_key": "recommend", "label": f"선택 {i}", "payload": {}},
        )
        assert res.status_code == 200

    list_res = client.get(
        "/api/recent-selections", headers=headers, params={"feature_key": "recommend"}
    )
    items = list_res.json()
    labels = [item["label"] for item in items]

    # MAX_ITEMS=3 -> 가장 오래된 "선택 0"은 잘려나가고, 최근 3개만 남아야 한다.
    assert len(items) == 3
    assert "선택 0" not in labels
    assert "선택 3" in labels


def test_recent_selections_are_isolated_per_user(signup_and_login):
    headers_a = signup_and_login("recent-user-a@example.com")
    headers_b = signup_and_login("recent-user-b@example.com")

    res = client.post(
        "/api/recent-selections",
        headers=headers_a,
        json={"feature_key": "ai-analysis", "label": "A의 선택", "payload": {}},
    )
    assert res.status_code == 200

    res_b = client.get(
        "/api/recent-selections", headers=headers_b, params={"feature_key": "ai-analysis"}
    )
    assert res_b.status_code == 200
    assert res_b.json() == []
