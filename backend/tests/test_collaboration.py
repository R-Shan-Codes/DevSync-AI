import subprocess
from pathlib import Path
from app.core.config import settings

def register(client, email, name):
    client.post("/api/v1/auth/register", json={"email": email, "display_name": name, "password": "secure-pass-123"})
    response = client.post("/api/v1/auth/login", data={"username": email, "password": "secure-pass-123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_review_and_test_run_workflow(client):
    admin = register(client, "admin@example.com", "Admin")
    project = client.post("/api/v1/projects", headers=admin, json={"name": "Workflow project"}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=admin, json={"title": "Build feature"}).json()
    review = client.post(f"/api/v1/projects/{project['id']}/reviews", headers=admin, json={"task_id": task["id"], "decision": "changes_requested", "summary": "Handle edge case"})
    assert review.status_code == 201
    run = client.post(f"/api/v1/projects/{project['id']}/test-runs", headers=admin, json={"task_id": task["id"], "result": "failed", "total": 4, "passed": 3, "failed": 1})
    assert run.status_code == 201
    assert client.get(f"/api/v1/projects/{project['id']}/reviews", headers=admin).json()[0]["decision"] == "changes_requested"
    assert client.get(f"/api/v1/projects/{project['id']}/test-runs", headers=admin).json()[0]["failed"] == 1

def test_test_run_count_validation(client):
    admin = register(client, "qa@example.com", "QA")
    project = client.post("/api/v1/projects", headers=admin, json={"name": "Validation project"}).json()
    task = client.post(f"/api/v1/projects/{project['id']}/tasks", headers=admin, json={"title": "Test validation"}).json()
    response = client.post(f"/api/v1/projects/{project['id']}/test-runs", headers=admin, json={"task_id": task["id"], "result": "passed", "total": 2, "passed": 1, "failed": 1})
    assert response.status_code == 422

def test_git_sync_and_status(client, tmp_path, monkeypatch):
    admin = register(client, "git@example.com", "Git User")
    project = client.post("/api/v1/projects", headers=admin, json={"name": "Git project"}).json()
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test Author"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    (repo / "README.md").write_text("first commit", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial commit"], check=True, capture_output=True)
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    sync = client.post(f"/api/v1/projects/{project['id']}/git/sync", headers=admin, json={"repository_path": "sample-repo"})
    assert sync.status_code == 200, sync.text
    assert len(sync.json()) == 1
    again = client.post(f"/api/v1/projects/{project['id']}/git/sync", headers=admin, json={"repository_path": "sample-repo"})
    assert again.status_code == 200
    assert again.json() == []
    status = client.get(f"/api/v1/projects/{project['id']}/git/status", headers=admin, params={"repository_path": "sample-repo"})
    assert status.status_code == 200
    assert status.json()["clean"] is True

def test_git_path_traversal_rejected(client, tmp_path, monkeypatch):
    admin = register(client, "safe@example.com", "Safe User")
    project = client.post("/api/v1/projects", headers=admin, json={"name": "Safe project"}).json()
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    response = client.get(f"/api/v1/projects/{project['id']}/git/status", headers=admin, params={"repository_path": ".."})
    assert response.status_code == 400
