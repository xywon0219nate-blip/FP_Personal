"""
tests/conftest.py
------------------
모든 테스트가 공유하는 설정.

배경
----
`main.py`는 모듈 최상단(=import 시점)에서 바로
    Base.metadata.create_all(bind=engine)
를 실행해서 테이블을 만든다. 이 `engine`은 `database/connection.py`에서 만든
"진짜" MySQL 엔진이라서, `main`을 import하기만 해도 실제 DB에 접속을 시도한다.
로컬에 `.env`가 있으면 문제없이 동작하지만, `.env`는 `.gitignore`에 포함돼 있어
GitHub Actions(CI)에는 올라가지 않는다. 즉 지금까지는:

- 로컬(실제 .env 존재): 테스트 통과
- CI(.env 없음): `database/connection.py`의 값 검증에서 곧바로 RuntimeError,
  혹은 값이 있어도 실제 MySQL에 연결할 수 없어 `import main` 단계에서부터 실패

이 파일은 아래 순서로 이 문제를 해결한다.

1. DB 관련 필수 환경변수가 비어있으면(로컬 무설정 / CI) 테스트 전용 더미 값으로
   채운다 (이미 값이 있으면 그대로 둔다 - 실제 `.env`를 덮어쓰지 않음).
2. `main`을 import하기 **전에**, `database.connection.engine`과 `.SessionLocal`을
   테스트 전용 SQLite 인메모리 엔진으로 교체한다. 이렇게 하면 `main.py`의
   `Base.metadata.create_all(bind=engine)`이 SQLite에 테이블을 만들게 되어,
   실제 MySQL은 전혀 필요 없어진다. (`router/inference.py`처럼 raw `engine`을
   직접 import해서 쓰는 모듈들도 같은 시점 이후에 import되므로 함께 안전해진다.)
3. FastAPI의 `get_db` 의존성도 명시적으로 같은 SQLite 세션으로 오버라이드한다.
4. 서버 시작 시 실행되는 `preload()`(추천 모델 로드 + 실데이터 피처 계산)는
   진짜 store 테이블 데이터를 전제로 하므로, 비어있는 테스트 DB에서는 의미가
   없어 no-op으로 대체한다.
"""
import os

_TEST_ENV_DEFAULTS = {
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "DB_HOST": "localhost",
    "DB_PORT": "3306",
    "DB_NAME": "test",
    "SECRET_KEY": "test-secret-key-for-ci",
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import database.connection as db_conn  # noqa: E402

# ── 테스트 전용 SQLite 인메모리 DB ──
# StaticPool + check_same_thread=False: 요청마다 새 세션을 만들지만 같은
# 인메모리 DB(데이터)를 계속 공유해야 하므로 필요한 조합.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

# `main`을 import하기 전에 교체해야, 그 안에서 실행되는
# `Base.metadata.create_all(bind=engine)`이 SQLite를 대상으로 실행된다.
db_conn.engine = test_engine
db_conn.SessionLocal = TestingSessionLocal

import main  # noqa: E402  (이 시점에 SQLite에 테이블이 생성됨)

# 실제 store 테이블 데이터를 전제로 한 무거운 사전 로드는 테스트에서 불필요.
main.preload = lambda: None


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


main.app.dependency_overrides[db_conn.get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _clean_tables():
    """테스트마다 모든 테이블을 비워서 테스트 간 서로 영향을 주지 않게 한다."""
    yield
    with test_engine.begin() as conn:
        for table in reversed(db_conn.Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def signup_and_login():
    """회원가입 + 로그인까지 마친 뒤 Authorization 헤더를 반환하는 헬퍼 팩토리.

    사용 예:
        def test_x(signup_and_login):
            headers = signup_and_login("a@example.com")
            client.get("/api/chat/sessions", headers=headers)
    """
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    def _make(email: str = "tester@example.com", password: str = "password123!"):
        res = client.post("/api/auth/signup/interests", json={
            "name": "테스터",
            "email": email,
            "password": password,
            "phone": "010-0000-0000",
            "categories": [],
            "regions": [],
            "storeTypes": [],
        })
        assert res.status_code == 200, res.text
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
