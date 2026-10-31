def register(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "display_name": "Member", "password": "secure-pass-123"})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": "secure-pass-123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_pipeline_reports_task_stage_and_next_action(client):
    headers = register(client, "pipeline@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Pipeline project"}).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        headers=headers,
        json={"title": "Build API"},
    ).json()

    response = client.get(f"/api/v1/projects/{project['id']}/pipeline", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_tasks"] == 1
    assert payload["stage_counts"] == {"coding": 1}
    assert payload["tasks"][0]["task_id"] == task["id"]
    assert payload["tasks"][0]["next_action"] == "Start coding"
    assert payload["tasks"][0]["ready_for_next_step"] is True


def test_pipeline_marks_incomplete_prerequisite_as_blocker(client):
    headers = register(client, "pipeline-dependency@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Dependency project"}).json()
    project_id = project["id"]
    prerequisite = client.post(
        f"/api/v1/projects/{project_id}/tasks", headers=headers,
        json={"title": "Create database"},
    ).json()
    dependent = client.post(
        f"/api/v1/projects/{project_id}/tasks", headers=headers,
        json={"title": "Build API"},
    ).json()

    dependency = client.post(
        f"/api/v1/projects/{project_id}/tasks/{dependent['id']}/dependencies",
        headers=headers,
        json={"depends_on_task_id": prerequisite["id"]},
    )
    assert dependency.status_code in (200, 201)

    response = client.get(f"/api/v1/projects/{project_id}/pipeline", headers=headers)
    assert response.status_code == 200
    row = next(item for item in response.json()["tasks"] if item["task_id"] == dependent["id"])
    assert "prerequisites_incomplete" in row["gates"]
    assert row["prerequisites"][0]["task_id"] == prerequisite["id"]
    assert row["ready_for_next_step"] is False


def test_pipeline_is_project_scoped(client):
    first = register(client, "pipeline-owner@example.com")
    second = register(client, "pipeline-outsider@example.com")
    project = client.post("/api/v1/projects", headers=first, json={"name": "Private pipeline"}).json()

    response = client.get(f"/api/v1/projects/{project['id']}/pipeline", headers=second)

    assert response.status_code == 404  # Project membership intentionally hides private project existence.
