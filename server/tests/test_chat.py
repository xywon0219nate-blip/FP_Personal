"""
router/chat.py 테스트.

주의: POST /api/chat(실제 챗봇 응답 생성)은 내부적으로 OpenAI API를 호출하므로
(네트워크/실제 API 키 필요) 이 테스트 스위트에서는 다루지 않는다. 여기서는
인증 검증과, OpenAI 호출 없이도 확인 가능한 세션 조회/삭제 경로를 검증한다.
"""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_post_chat_without_token_returns_401():
    res = client.post("/api/chat", json={"message": "안녕하세요"})
    assert res.status_code == 401


def test_list_sessions_without_token_returns_401():
    res = client.get("/api/chat/sessions")
    assert res.status_code == 401


def test_delete_session_without_token_returns_401():
    res = client.delete("/api/chat/sessions/1")
    assert res.status_code == 401


def test_new_user_has_no_chat_sessions(signup_and_login):
    headers = signup_and_login("chat-user1@example.com")
    res = client.get("/api/chat/sessions", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_history_for_unknown_session_returns_404(signup_and_login):
    headers = signup_and_login("chat-user2@example.com")
    res = client.get("/api/chat/999999/history", headers=headers)
    assert res.status_code == 404


def test_delete_unknown_session_returns_404(signup_and_login):
    headers = signup_and_login("chat-user3@example.com")
    res = client.delete("/api/chat/sessions/999999", headers=headers)
    assert res.status_code == 404


def test_cannot_read_another_users_session_history(signup_and_login):
    """세션 조회가 user_id 기준으로 스코프되는지 확인한다.

    OpenAI 호출 없이(=handle_chat을 거치지 않고) 소유자의 세션을 DB에 직접 만든 뒤,
    다른 사용자가 그 session_id로 접근하면 404가 나야 한다 (권한 없는 세션 열람 방지).
    """
    from tests.conftest import TestingSessionLocal
    from models.user import User
    from models.chat import ChatSession

    headers_owner = signup_and_login("chat-owner@example.com")
    headers_intruder = signup_and_login("chat-intruder@example.com")

    db = TestingSessionLocal()
    try:
        owner = db.query(User).filter(User.email == "chat-owner@example.com").first()
        session = ChatSession(user_id=owner.id, title="owner의 상담")
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    finally:
        db.close()

    res_owner = client.get(f"/api/chat/{session_id}/history", headers=headers_owner)
    assert res_owner.status_code == 200
    assert res_owner.json()["session_id"] == session_id

    res_intruder = client.get(f"/api/chat/{session_id}/history", headers=headers_intruder)
    assert res_intruder.status_code == 404
