"""
router/recommend.py 테스트.

POST /api/recommendation이 실제로 추천 결과를 만들어내는 "성공 경로"는
router/inference.py가 store 테이블 실데이터 + 학습된 모델(recommendation_model.pkl)을
전제로 하므로, 여기서는 검증(validation)/에러 경로 위주로 확인한다.
"""
from fastapi.testclient import TestClient
from main import app
from tests.conftest import TestingSessionLocal
from models.category import MajorCategory, SubCategory

client = TestClient(app)


def _seed_one_category():
    db = TestingSessionLocal()
    try:
        major = MajorCategory(code="CS1", name="외식업")
        db.add(major)
        db.flush()
        db.add(SubCategory(code="CS100001", name="한식음식점", major_id=major.id))
        db.commit()
    finally:
        db.close()


def test_get_regions_returns_all_25_seoul_districts():
    res = client.get("/api/regions")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 25
    assert {"code": "11680", "name": "강남구"} in body


def test_get_categories_returns_a_list():
    res = client.get("/api/categories")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_get_store_types_returns_a_list():
    res = client.get("/api/store-types")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_recommendation_missing_region_returns_422():
    res = client.post("/api/recommendation", json={"majorCategories": ["CS1"]})
    assert res.status_code == 422


def test_recommendation_empty_region_returns_400():
    res = client.post(
        "/api/recommendation", json={"region": "", "majorCategories": ["CS1"]}
    )
    assert res.status_code == 400


def test_recommendation_without_any_category_returns_400():
    res = client.post("/api/recommendation", json={"region": "11680"})
    assert res.status_code == 400


def test_recommendation_with_non_numeric_region_returns_400():
    # majorCategories가 실제 존재하는 코드여야 "카테고리 없음" 400이 아니라
    # region 검증 단계(int 변환)까지 도달한다 - 그래서 카테고리를 미리 심어둔다.
    _seed_one_category()
    res = client.post(
        "/api/recommendation",
        json={"region": "강남구", "majorCategories": ["CS1"]},
    )
    assert res.status_code == 400
