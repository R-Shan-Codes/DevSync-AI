def register(client, email):
    client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Project Owner", "password": "secure-pass-123"
    })
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "secure-pass-123"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_project_and_tasks(client, email):
    headers = register(client, email)
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Intelligence project"}).json()
    first = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=headers,
                        json={"title": "Build API"}).json()
    second = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=headers,
                         json={"title": "Build UI"}).json()
    return headers, project, first, second


def test_development_events_and_file_changes_are_persisted(client):
    headers, project, _, task = create_project_and_tasks(client, "events@example.com")
    pid = project["id"]
    response = client.post(f"/api/v1/projects/{pid}/intelligence/events", headers=headers, json={
        "events": [
            {"event_type": "file.changed", "payload": {"path": "src/App.tsx", "task_id": task["id"], "branch": "feature/ui"}},
            {"event_type": "branch.changed", "payload": {"branch": "feature/ui"}}
        ]
    })
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 2
    assert len(client.get(f"/api/v1/projects/{pid}/intelligence/events", headers=headers).json()) == 2
    files = client.get(f"/api/v1/projects/{pid}/intelligence/files", headers=headers).json()
    assert files[0]["path"] == "src/App.tsx"
    assert files[0]["task_id"] == task["id"]


def test_development_event_rejects_path_traversal(client):
    headers, project, _, _ = create_project_and_tasks(client, "event-safe@example.com")
    response = client.post(f"/api/v1/projects/{project['id']}/intelligence/events", headers=headers, json={
        "events": [{"event_type": "file.changed", "payload": {"path": "../secrets.env"}}]
    })
    assert response.status_code == 422


def test_task_dependencies_prevent_cycles(client):
    headers, project, first, second = create_project_and_tasks(client, "dependencies@example.com")
    pid = project["id"]
    added = client.post(f"/api/v1/projects/{pid}/tasks/{first['id']}/dependencies", headers=headers,
                        json={"depends_on_task_id": second["id"]})
    assert added.status_code == 201, added.text
    cycle = client.post(f"/api/v1/projects/{pid}/tasks/{second['id']}/dependencies", headers=headers,
                        json={"depends_on_task_id": first["id"]})
    assert cycle.status_code == 409
    listed = client.get(f"/api/v1/projects/{pid}/tasks/{first['id']}/dependencies", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["depends_on_task_id"] == second["id"]


def test_ai_conversations_and_human_override_are_persistent(client):
    headers, project, task, _ = create_project_and_tasks(client, "memory-chat@example.com")
    pid = project["id"]
    role = client.get(f"/api/v1/projects/{pid}/members/me", headers=headers).json()["role"]
    conversation = client.post(f"/api/v1/projects/{pid}/ai/conversations", headers=headers,
                               json={"role": role, "title": "Implementation discussion"})
    assert conversation.status_code == 201, conversation.text
    cid = conversation.json()["id"]
    listed = client.get(f"/api/v1/projects/{pid}/ai/conversations", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == cid

    recommendation = client.post(f"/api/v1/projects/{pid}/ai/recommendations", headers=headers, json={
        "task_id": task["id"], "recommendation_type": "task_status",
        "proposed_value": "ready_for_testing", "rationale": "Implementation evidence is complete",
        "evidence": [{"type": "commit", "hash": "abc123"}]
    })
    assert recommendation.status_code == 201, recommendation.text
    rid = recommendation.json()["id"]
    override = client.post(f"/api/v1/projects/{pid}/ai/recommendations/{rid}/override", headers=headers,
                           json={"decision": "rejected", "reason": "QA documentation is still missing"})
    assert override.status_code == 200, override.text
    assert override.json()["status"] == "rejected"
    assert client.get(f"/api/v1/projects/{pid}/ai/recommendations", headers=headers).json()[0]["status"] == "rejected"

    modified = client.post(f"/api/v1/projects/{pid}/ai/recommendations", headers=headers, json={
        "task_id": task["id"], "recommendation_type": "task_status",
        "proposed_value": "ready_for_testing", "rationale": "Initial recommendation"
    }).json()
    missing_value = client.post(
        f"/api/v1/projects/{pid}/ai/recommendations/{modified['id']}/override", headers=headers,
        json={"decision": "modified", "reason": "Keep the task in progress"}
    )
    assert missing_value.status_code == 422
    changed = client.post(
        f"/api/v1/projects/{pid}/ai/recommendations/{modified['id']}/override", headers=headers,
        json={"decision": "modified", "reason": "A final review remains", "replacement_value": "in_progress"}
    )
    assert changed.status_code == 200
    assert changed.json()["replacement_value"] == "in_progress"


def test_developer_handover_is_persisted(client):
    headers, project, _, _ = create_project_and_tasks(client, "handover@example.com")
    pid = project["id"]
    created = client.post(f"/api/v1/projects/{pid}/handover", headers=headers, json={
        "summary": "API endpoint implemented; integration test pending.",
        "pending_items": ["Add integration test"],
        "blockers": ["Waiting for API contract review"]
    })
    assert created.status_code == 201, created.text
    history = client.get(f"/api/v1/projects/{pid}/handover", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["pending_items"] == ["Add integration test"]
