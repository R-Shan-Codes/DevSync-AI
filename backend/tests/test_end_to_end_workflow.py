def register(client, email):
    client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "End-to-end Developer", "password": "secure-pass-123"
    })
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "secure-pass-123"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_task_to_commit_to_review_to_qa_to_merge_end_to_end(client):
    headers = register(client, "end-to-end-workflow@example.com")
    project = client.post(
        "/api/v1/projects", headers=headers, json={"name": "End-to-end delivery"}
    ).json()
    project_id = project["id"]
    task = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={
            "title": "Implement OAuth token refresh",
            "description": "Refresh expired OAuth access tokens safely.",
        },
    ).json()
    task_id = task["id"]

    # Editor telemetry records files, branch and commit metadata without source contents.
    commit_hash = "b" * 40
    telemetry = client.post(
        f"/api/v1/projects/{project_id}/intelligence/events",
        headers=headers,
        json={"events": [
            {"event_type": "workspace.opened", "payload": {"workspace": "DevSync-AI"}},
            {"event_type": "file.changed", "payload": {
                "path": "backend/app/auth.py", "branch": "feature/oauth-refresh", "task_id": task_id
            }},
            {"event_type": "branch.changed", "payload": {"branch": "feature/oauth-refresh"}},
            {"event_type": "commit.created", "payload": {
                "commit_hash": commit_hash,
                "message": "Implement OAuth token refresh handling",
                "author": "End-to-end Developer",
                "author_email": "developer@example.com",
                "committed_at": "2026-10-31T12:00:00Z",
                "branch": "feature/oauth-refresh",
                "repository_path": "DevSync-AI",
            }},
        ]},
    )
    assert telemetry.status_code == 202, telemetry.text
    assert telemetry.json()["accepted"] == 4

    events = client.get(
        f"/api/v1/projects/{project_id}/intelligence/events", headers=headers
    ).json()
    assert {event["event_type"] for event in events} >= {
        "workspace.opened", "file.changed", "branch.changed", "commit.created"
    }

    # The commit becomes a heuristic candidate; a human explicitly confirms the link.
    suggestions = client.get(
        f"/api/v1/projects/{project_id}/intelligence/commit-task-suggestions",
        headers=headers,
    ).json()["suggestions"]
    candidate = next(item for item in suggestions if item["commit_hash"] == commit_hash)
    match = next(item for item in candidate["candidates"] if item["task_id"] == task_id)
    linked = client.post(
        f"/api/v1/projects/{project_id}/intelligence/commit-links",
        headers=headers,
        json={"commit_hash": commit_hash, "task_id": task_id, "confidence": match["confidence"]},
    )
    assert linked.status_code == 201, linked.text

    # Follow the explicit delivery state machine with persisted review and QA evidence.
    for status in ("in_progress", "submitted", "in_review"):
        response = client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task_id}",
            headers=headers,
            json={"status": status},
        )
        assert response.status_code == 200, response.text

    review = client.post(
        f"/api/v1/projects/{project_id}/reviews",
        headers=headers,
        json={
            "task_id": task_id,
            "decision": "approved",
            "summary": "OAuth refresh implementation reviewed.",
            "findings": "No blocking findings.",
        },
    )
    assert review.status_code == 201, review.text

    for status in ("approved", "ready_for_testing", "testing"):
        response = client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task_id}",
            headers=headers,
            json={"status": status},
        )
        assert response.status_code == 200, response.text

    test_run = client.post(
        f"/api/v1/projects/{project_id}/test-runs",
        headers=headers,
        json={
            "task_id": task_id,
            "result": "passed",
            "summary": "OAuth refresh integration tests passed.",
            "total": 8,
            "passed": 8,
            "failed": 0,
        },
    )
    assert test_run.status_code == 201, test_run.text

    for status in ("passed", "ready_for_merge", "merged"):
        response = client.patch(
            f"/api/v1/projects/{project_id}/tasks/{task_id}",
            headers=headers,
            json={"status": status},
        )
        assert response.status_code == 200, response.text

    pipeline = client.get(
        f"/api/v1/projects/{project_id}/pipeline", headers=headers
    )
    assert pipeline.status_code == 200, pipeline.text
    task_row = next(row for row in pipeline.json()["tasks"] if row["task_id"] == task_id)
    assert task_row["status"] == "merged"
    assert task_row["latest_review"]["decision"] == "approved"
    assert task_row["latest_test_run"]["result"] == "passed"

    commit_links = client.get(
        f"/api/v1/projects/{project_id}/intelligence/commit-links", headers=headers
    )
    assert commit_links.status_code == 200
    assert any(link["commit_hash"] == commit_hash and link["task_id"] == task_id
               for link in commit_links.json())
