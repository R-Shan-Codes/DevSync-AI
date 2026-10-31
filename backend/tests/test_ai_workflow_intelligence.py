from app.core.config import settings


def _headers(client, email="intelligence@example.com"):
    client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Intelligence Tester", "password": "secure-pass-123"
    })
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "secure-pass-123"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_commit_task_suggestions_and_summary_are_project_scoped(client):
    headers = _headers(client)
    project = client.post("/api/v1/projects", headers=headers,
                          json={"name": "Intelligence Project"}).json()
    project_id = project["id"]
    task = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers,
                       json={"title": "Implement payment reconciliation"}).json()

    suggestions = client.get(
        f"/api/v1/projects/{project_id}/intelligence/commit-task-suggestions", headers=headers
    )
    summary = client.get(
        f"/api/v1/projects/{project_id}/intelligence/summary", headers=headers
    )
    assert suggestions.status_code == 200
    assert suggestions.json()["suggestions"] == []
    assert summary.status_code == 200
    assert summary.json()["development_events"] == 0
    assert summary.json()["pending_ai_recommendations"] == 0
    assert task["project_id"] == project_id


def test_ai_task_recommendations_require_gemini_configuration(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    headers = _headers(client, "no-gemini@example.com")
    project = client.post("/api/v1/projects", headers=headers,
                          json={"name": "AI Guard Project"}).json()
    client.post(f"/api/v1/projects/{project['id']}/tasks", headers=headers,
                json={"title": "Add workflow analytics"})
    response = client.post(
        f"/api/v1/projects/{project['id']}/ai/task-recommendations", headers=headers
    )
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]
