from fastapi.testclient import TestClient
from app.core.config import settings


def _auth(client: TestClient, email: str) -> dict[str, str]:
    password = "secure-pass-123"
    client.post("/api/v1/auth/register", json={"email": email, "display_name": "AI Chat Tester", "password": password})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_ai_conversations_persist_user_messages_when_provider_is_unconfigured(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    headers = _auth(client, "persistent-chat@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Persistent chat"}).json()
    project_id = project["id"]
    member = client.get(f"/api/v1/projects/{project_id}/members/me", headers=headers).json()

    created = client.post(
        f"/api/v1/projects/{project_id}/ai/conversations",
        headers=headers,
        json={"role": member["role"], "title": "Debug session"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    mismatch = client.post(
        f"/api/v1/projects/{project_id}/ai/conversations",
        headers=headers,
        json={"role": "tester_qa_engineer", "title": "Wrong role"},
    )
    assert mismatch.status_code == 403

    failed_provider = client.post(
        f"/api/v1/projects/{project_id}/ai/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Please help debug the authentication flow"},
    )
    assert failed_provider.status_code == 503
    messages = client.get(
        f"/api/v1/projects/{project_id}/ai/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert messages.status_code == 200
    assert len(messages.json()) == 1
    assert messages.json()[0]["sender"] == "user"
    assert messages.json()[0]["content"] == "Please help debug the authentication flow"
