def register(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "display_name": "Member", "password": "secure-pass-123"})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": "secure-pass-123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_insights_and_project_memory(client):
    headers = register(client, "memory@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Memory project"}).json()
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/tasks", headers=headers, json={"title": "Implement dashboard"})
    insights = client.get(f"/api/v1/ai/insights/{pid}", headers=headers)
    assert insights.status_code == 200
    assert insights.json()["total_tasks"] == 1
    assert "contribution_methodology" in insights.json()
    memory = client.get(f"/api/v1/projects/{pid}/memory", headers=headers)
    assert memory.status_code == 200
    assert memory.json()["tasks"][0]["title"] == "Implement dashboard"
    assert memory.json()["open_bugs"] == []
    assert memory.json()["recent_handovers"] == []

def test_ai_assistant_requires_configuration(client):
    headers = register(client, "assistant@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "AI project"}).json()
    member = client.get(f"/api/v1/projects/{project['id']}/members/me", headers=headers).json()
    response = client.post("/api/v1/ai/assist", headers=headers, json={"project_id": project["id"], "role": member["role"], "prompt": "Help implement a feature"})
    assert response.status_code in (200, 503)
