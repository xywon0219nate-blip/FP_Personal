"""
router/category_mapping.py 단위 테스트.

HTTP를 거치지 않고, tests/conftest.py가 만들어둔 테스트 전용 SQLite 세션에
MajorCategory/SubCategory를 직접 심어서 resolve_primary_codes /
resolve_reference_pool의 동작을 검증한다.
"""
from tests.conftest import TestingSessionLocal
from models.category import MajorCategory, SubCategory
from router.category_mapping import resolve_primary_codes, resolve_reference_pool


def _seed_categories(db):
    food = MajorCategory(code="CS1", name="외식업")
    service = MajorCategory(code="CS2", name="서비스업")
    db.add_all([food, service])
    db.flush()

    db.add_all([
        SubCategory(code="CS100001", name="한식음식점", major_id=food.id),
        SubCategory(code="CS100002", name="커피-음료", major_id=food.id),
        SubCategory(code="CS100003", name="중식음식점", major_id=food.id),
        SubCategory(code="CS200001", name="미용실", major_id=service.id),
    ])
    db.commit()


def test_resolve_primary_codes_filters_to_existing_sub_categories():
    db = TestingSessionLocal()
    try:
        _seed_categories(db)
        codes = resolve_primary_codes(
            db, major_categories=[], sub_categories=["CS100001", "CS100002", "없는코드"]
        )
        # DB에 실존하지 않는 코드("없는코드")는 무시되고, 실존하는 것만 정렬돼 반환된다.
        assert codes == ["CS100001", "CS100002"]
    finally:
        db.close()


def test_resolve_primary_codes_expands_major_category_to_all_children():
    db = TestingSessionLocal()
    try:
        _seed_categories(db)
        codes = resolve_primary_codes(db, major_categories=["CS1"], sub_categories=[])
        assert codes == ["CS100001", "CS100002", "CS100003"]
    finally:
        db.close()


def test_resolve_primary_codes_returns_empty_when_nothing_selected():
    db = TestingSessionLocal()
    try:
        assert resolve_primary_codes(db, major_categories=[], sub_categories=[]) == []
    finally:
        db.close()


def test_resolve_reference_pool_excludes_already_checked_codes():
    db = TestingSessionLocal()
    try:
        _seed_categories(db)
        pool = resolve_reference_pool(
            db, major_categories=["CS1"], sub_categories=["CS100001", "CS100002"]
        )
        # CS1(외식업) 전체 중 이미 체크한 CS100001/CS100002는 빠지고 CS100003만 남아야 한다.
        assert pool == ["CS100003"]
    finally:
        db.close()


def test_resolve_reference_pool_is_empty_when_no_sub_category_checked():
    db = TestingSessionLocal()
    try:
        _seed_categories(db)
        # sub_categories가 아예 없으면(대분류만 선택) 제외할 대상이 없으므로 빈 리스트.
        pool = resolve_reference_pool(db, major_categories=["CS1"], sub_categories=[])
        assert pool == []
    finally:
        db.close()
