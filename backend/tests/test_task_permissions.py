from fastapi.testclient import TestClient


def _register(client: TestClient, email: str) -> dict:
    password = "secure-pass-123"
    client.post("/api/v1/auth/register", json={"email": email, "display_name": "Permission Tester", "password": password})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_task_routes_enforce_view_and_edit_permissions(client: TestClient):
    owner = _register(client, "task-permission-owner@example.com")
    member_headers = _register(client, "task-permission-member@example.com")
    project = client.post("/api/v1/projects", headers=owner, json={"name": "Permission project"}).json()
    project_id = project["id"]
    added = client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=owner,
        json={"email": "task-permission-member@example.com", "role": "frontend_developer"},
    )
    assert added.status_code == 201
    member_id = added.json()["id"]
    updated = client.patch(
        f"/api/v1/projects/{project_id}/members/{member_id}",
        headers=owner,
        json={"permissions": {"view": False, "edit": False}},
    )
    assert updated.status_code == 200

    task = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=owner,
        json={"title": "Restricted task"},
    ).json()
    listing = client.get(f"/api/v1/projects/{project_id}/tasks", headers=member_headers)
    assert listing.status_code == 403
    transition = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task['id']}",
        headers=member_headers,
        json={"status": "in_progress"},
    )
    assert transition.status_code == 403


def test_review_permission_can_advance_review_stage_without_edit_permission(client: TestClient):
    owner = _register(client, "review-permission-owner@example.com")
    reviewer = _register(client, "review-permission-user@example.com")
    project = client.post("/api/v1/projects", headers=owner, json={"name": "Review permission project"}).json()
    project_id = project["id"]
    added = client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=owner,
        json={"email": "review-permission-user@example.com", "role": "security_engineer"},
    )
    assert added.status_code == 201
    member_id = added.json()["id"]
    changed = client.patch(
        f"/api/v1/projects/{project_id}/members/{member_id}",
        headers=owner,
        json={"permissions": {"edit": False, "review": True}},
    )
    assert changed.status_code == 200

    task = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=owner,
        json={"title": "Review gated task"},
    ).json()
    for stage in ("in_progress", "submitted"):
        result = client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task['id']}",
            headers=owner,
            json={"status": stage},
        )
        assert result.status_code == 200
    review = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task['id']}",
        headers=reviewer,
        json={"status": "in_review"},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "in_review"
