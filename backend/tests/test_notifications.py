from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str) -> dict[str, str]:
    password = "secure-pass-123"
    client.post("/api/v1/auth/register", json={"email": email, "display_name": "Notification Tester", "password": password})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_task_assignment_notifications_are_private_and_readable(client: TestClient):
    owner = _auth(client, "notification-owner@example.com")
    assignee = _auth(client, "notification-assignee@example.com")
    project = client.post("/api/v1/projects", headers=owner, json={"name": "Notification project"}).json()
    project_id = project["id"]
    added = client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=owner,
        json={"email": "notification-assignee@example.com", "role": "frontend_developer"},
    )
    assert added.status_code == 201
    assignee_id = added.json()["user_id"]

    task = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=owner,
        json={"title": "Implement notification inbox", "assignee_id": assignee_id},
    )
    assert task.status_code == 201

    inbox = client.get("/api/v1/notifications", headers=assignee)
    assert inbox.status_code == 200
    assert inbox.json()["unread_count"] == 1
    notification = inbox.json()["items"][0]
    assert notification["type"] == "task.assigned"
    assert "Implement notification inbox" in notification["message"]
    assert notification["read_at"] is None

    owner_inbox = client.get("/api/v1/notifications", headers=owner)
    assert owner_inbox.status_code == 200
    assert owner_inbox.json()["items"] == []

    marked = client.patch(f"/api/v1/notifications/{notification['id']}/read", headers=assignee)
    assert marked.status_code == 200
    assert client.get("/api/v1/notifications?unread_only=true", headers=assignee).json()["unread_count"] == 0

    # The assignee is notified when someone else advances the task.
    progressed = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task.json()['id']}",
        headers=owner,
        json={"status": "in_progress"},
    )
    assert progressed.status_code == 200
    next_inbox = client.get("/api/v1/notifications?unread_only=true", headers=assignee)
    assert next_inbox.json()["unread_count"] == 1
    assert next_inbox.json()["items"][0]["type"] == "task.status_changed"


def test_notification_read_operations_cannot_access_another_users_notification(client: TestClient):
    owner = _auth(client, "notification-private-owner@example.com")
    assignee = _auth(client, "notification-private-assignee@example.com")
    project = client.post("/api/v1/projects", headers=owner, json={"name": "Private notifications"}).json()
    project_id = project["id"]
    member = client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=owner,
        json={"email": "notification-private-assignee@example.com", "role": "frontend_developer"},
    ).json()
    task = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=owner,
        json={"title": "Private notification task", "assignee_id": member["user_id"]},
    ).json()
    notification = client.get("/api/v1/notifications", headers=assignee).json()["items"][0]
    forbidden = client.patch(f"/api/v1/notifications/{notification['id']}/read", headers=owner)
    assert forbidden.status_code == 404
