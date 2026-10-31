from fastapi.testclient import TestClient

def _headers(client: TestClient, email: str) -> dict[str, str]:
    password = "secure-pass-123"
    client.post("/api/v1/auth/register", json={"email": email, "display_name": "Task Search", "password": password})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_task_search_filters_and_pagination_are_project_scoped(client: TestClient):
    headers = _headers(client, "task-search@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Search project"}).json()
    project_id = project["id"]
    member = client.get(f"/api/v1/projects/{project_id}/members/me", headers=headers).json()
    first = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers, json={
        "title": "Build authentication service", "description": "Implement secure login",
        "priority": "urgent", "assignee_id": member["user_id"],
    })
    second = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers, json={
        "title": "Design dashboard layout", "description": "Responsive frontend", "priority": "low",
    })
    assert first.status_code == 201 and second.status_code == 201
    by_text = client.get(f"/api/v1/projects/{project_id}/tasks?q=authentication", headers=headers)
    assert by_text.status_code == 200
    assert [task["id"] for task in by_text.json()] == [first.json()["id"]]
    by_priority_and_assignee = client.get(f"/api/v1/projects/{project_id}/tasks?priority=urgent&assignee_id={member['user_id']}", headers=headers)
    assert [task["id"] for task in by_priority_and_assignee.json()] == [first.json()["id"]]
    invalid_priority = client.get(f"/api/v1/projects/{project_id}/tasks?priority=impossible", headers=headers)
    assert invalid_priority.status_code == 422
    page = client.get(f"/api/v1/projects/{project_id}/tasks?limit=1&offset=0", headers=headers)
    assert len(page.json()) == 1
