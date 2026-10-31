from fastapi.testclient import TestClient


def _owner_headers(client: TestClient, email: str) -> dict[str, str]:
    password = "secure-pass-123"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Workflow Owner", "password": password},
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert logged_in.status_code == 200
    return {"Authorization": f"Bearer {logged_in.json()['access_token']}"}


def test_complete_development_pipeline_and_reject_skipped_stage(client: TestClient):
    headers = _owner_headers(client, "pipeline-owner@example.com")
    project = client.post(
        "/api/v1/projects", headers=headers, json={"name": "Pipeline integration"}
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    created = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={"title": "Implement core workflow", "description": "Exercise every delivery stage"},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    skipped = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        headers=headers,
        json={"status": "merged"},
    )
    assert skipped.status_code == 409

    stages = [
        "in_progress", "submitted", "in_review", "approved",
        "ready_for_testing", "testing", "passed", "ready_for_merge", "merged",
    ]
    for stage in stages:
        response = client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task_id}",
            headers=headers,
            json={"status": stage},
        )
        assert response.status_code == 200, (stage, response.text)
        assert response.json()["status"] == stage

    activity = client.get(f"/api/v1/projects/{project_id}/activity", headers=headers)
    assert activity.status_code == 200
    assert any(
        item["event_type"] == "task.status_changed"
        and item["payload"].get("to") == "merged"
        for item in activity.json()
    )
