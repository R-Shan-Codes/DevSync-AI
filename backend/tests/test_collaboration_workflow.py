def register(client, email):
    client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Workflow Member", "password": "secure-pass-123"
    })
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "secure-pass-123"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_collaboration_workflow_records_review_test_and_bug_evidence(client):
    headers = register(client, "collaboration-owner@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Collaboration project"}).json()
    project_id = project["id"]
    task = client.post(
        f"/api/v1/projects/{project_id}/tasks", headers=headers,
        json={"title": "Implement sign-in flow"}
    ).json()

    review = client.post(f"/api/v1/projects/{project_id}/reviews", headers=headers, json={
        "task_id": task["id"], "decision": "approved",
        "summary": "Implementation is ready for QA.",
        "findings": "No blocking findings."
    })
    assert review.status_code == 201, review.text
    assert review.json()["decision"] == "approved"

    run = client.post(f"/api/v1/projects/{project_id}/test-runs", headers=headers, json={
        "task_id": task["id"], "result": "passed", "summary": "Login and logout smoke tests passed.",
        "total": 4, "passed": 4, "failed": 0
    })
    assert run.status_code == 201, run.text
    assert run.json()["passed"] == 4

    bug = client.post(f"/api/v1/projects/{project_id}/bugs", headers=headers, json={
        "task_id": task["id"], "title": "Validation message is unclear",
        "description": "The invalid email message does not explain the required format.",
        "severity": "low"
    })
    assert bug.status_code == 201, bug.text

    assert client.get(f"/api/v1/projects/{project_id}/reviews", headers=headers).json()[0]["id"] == review.json()["id"]
    assert client.get(f"/api/v1/projects/{project_id}/test-runs", headers=headers).json()[0]["id"] == run.json()["id"]
    assert client.get(f"/api/v1/projects/{project_id}/bugs?status=open", headers=headers).json()[0]["id"] == bug.json()["id"]

    pipeline = client.get(f"/api/v1/projects/{project_id}/pipeline", headers=headers).json()
    row = next(item for item in pipeline["tasks"] if item["task_id"] == task["id"])
    assert row["latest_review"]["decision"] == "approved"
    assert row["latest_test_run"]["result"] == "passed"
    assert row["open_bug_count"] == 1


def test_collaboration_workflow_rejects_foreign_task_and_invalid_test_counts(client):
    owner = register(client, "collaboration-scope-owner@example.com")
    outsider = register(client, "collaboration-scope-outsider@example.com")
    project = client.post("/api/v1/projects", headers=owner, json={"name": "Scoped workflow"}).json()
    foreign_project = client.post("/api/v1/projects", headers=outsider, json={"name": "Other workflow"}).json()
    foreign_task = client.post(
        f"/api/v1/projects/{foreign_project['id']}/tasks", headers=outsider,
        json={"title": "Foreign task"}
    ).json()
    project_id = project["id"]

    review = client.post(f"/api/v1/projects/{project_id}/reviews", headers=owner, json={
        "task_id": foreign_task["id"], "decision": "approved"
    })
    assert review.status_code == 404

    test_run = client.post(f"/api/v1/projects/{project_id}/test-runs", headers=owner, json={
        "task_id": foreign_task["id"], "result": "passed", "total": 2, "passed": 1, "failed": 1
    })
    assert test_run.status_code == 422  # Passed results cannot contain failed tests.

    foreign_task_run = client.post(f"/api/v1/projects/{project_id}/test-runs", headers=owner, json={
        "task_id": foreign_task["id"], "result": "passed", "total": 1, "passed": 1, "failed": 0
    })
    assert foreign_task_run.status_code == 404
