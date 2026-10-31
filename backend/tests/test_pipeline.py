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
    assert payload["tasks"][0]["assignment_suggestions"]
    assert payload["tasks"][0]["assignment_suggestions"][0]["user_id"]


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


def test_pipeline_surfaces_task_linked_ai_review_as_advisory_evidence(client):
    import json
    from app.core.database import get_db
    from app.main import app
    from app.models import AIReviewArtifact, AIReviewTaskLink, User

    headers = register(client, "pipeline-ai-evidence@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "AI evidence pipeline"}).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        headers=headers,
        json={"title": "Fix token refresh"},
    ).json()

    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        user = db.query(User).filter_by(email="pipeline-ai-evidence@example.com").one()
        artifact = AIReviewArtifact(
            project_id=project["id"],
            requester_id=user.id,
            artifact_type="pull_request_review",
            source_key="pr:51",
            summary="Review identified a possible token refresh race.",
            findings=json.dumps([{"severity": "high", "title": "Race condition"}]),
        )
        db.add(artifact)
        db.commit()
        db.add(AIReviewTaskLink(
            artifact_id=artifact.id,
            project_id=project["id"],
            task_id=task["id"],
            linked_by_id=user.id,
        ))
        db.commit()
    finally:
        generator.close()

    response = client.get(f"/api/v1/projects/{project['id']}/pipeline", headers=headers)
    assert response.status_code == 200
    row = next(item for item in response.json()["tasks"] if item["task_id"] == task["id"])
    assert row["latest_ai_review"]["source_key"] == "pr:51"
    assert row["latest_ai_review"]["finding_count"] == 1
    # AI findings are advisory and do not silently block or advance the task.
    assert row["status"] == "backlog"
    assert row["ready_for_next_step"] is True
