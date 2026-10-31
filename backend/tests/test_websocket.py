from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _register_and_login(client: TestClient, email: str) -> str:
    password = "secure-pass-123"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Realtime Tester", "password": password},
    )
    assert response.status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_project_websocket_accepts_member_and_answers_ping(client: TestClient):
    token = _register_and_login(client, "ws-member@example.com")
    project_response = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Realtime project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    with client.websocket_connect(f"/ws/projects/{project_id}?token={token}") as websocket:
        websocket.send_text("ping")
        assert websocket.receive_json() == {"type": "pong"}


def test_project_websocket_rejects_missing_token(client: TestClient):
    try:
        with client.websocket_connect("/ws/projects/not-a-project"):
            assert False, "A socket without a token must be rejected"
    except WebSocketDisconnect as exc:
        assert exc.code == 4401


def test_project_websocket_rejects_non_member(client: TestClient):
    owner_token = _register_and_login(client, "ws-owner@example.com")
    outsider_token = _register_and_login(client, "ws-outsider@example.com")
    project_response = client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Private realtime project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    try:
        with client.websocket_connect(
            f"/ws/projects/{project_id}?token={outsider_token}"
        ):
            assert False, "A non-member must not be allowed to join a project socket"
    except WebSocketDisconnect as exc:
        assert exc.code == 4403
