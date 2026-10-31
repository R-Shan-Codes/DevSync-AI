import hashlib
import hmac
import json

from app.core import config
from app.core.database import get_db
from app.main import app
from app.models import ActivityEvent, GitEvent, GitHubWebhookDelivery, Project


def _project_with_repository(client, email):
    client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Webhook Tester", "password": "secure-pass-123"
    })
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "secure-pass-123"
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Webhook Project"}).json()
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        record = db.get(Project, project["id"])
        record.github_repo_full_name = "acme/devsync"
        record.github_repo_url = "https://github.com/acme/devsync"
        record.github_default_branch = "main"
        db.commit()
    finally:
        generator.close()
    return project["id"]


def _send_webhook(client, payload, event, delivery, secret, signature_secret=None):
    body = json.dumps(payload, separators=(",", ":")).encode()
    key = (signature_secret if signature_secret is not None else secret).encode()
    signature = "sha256=" + hmac.new(key, body, hashlib.sha256).hexdigest()
    return client.post("/api/v1/github/webhooks", content=body, headers={
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": event,
    })


def _db_session():
    generator = app.dependency_overrides[get_db]()
    return generator, next(generator)


def test_webhook_rejects_missing_configuration_and_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(config.settings, "github_webhook_secret", "")
    response = client.post("/api/v1/github/webhooks", content=b"{}")
    assert response.status_code == 503

    monkeypatch.setattr(config.settings, "github_webhook_secret", "test-webhook-secret")
    response = _send_webhook(
        client, {"repository": {"full_name": "acme/devsync"}}, "push",
        "invalid-signature-delivery", "test-webhook-secret", "wrong-secret"
    )
    assert response.status_code == 401


def test_push_webhook_persists_commits_and_deduplicates_delivery(client, monkeypatch):
    project_id = _project_with_repository(client, "push-webhook@example.com")
    secret = "test-webhook-secret"
    monkeypatch.setattr(config.settings, "github_webhook_secret", secret)
    commit_hash = "a" * 40
    payload = {
        "ref": "refs/heads/feature/webhooks",
        "before": "b" * 40,
        "after": commit_hash,
        "repository": {"full_name": "acme/devsync"},
        "sender": {"login": "contributor"},
        "commits": [{
            "id": commit_hash,
            "message": "Add webhook event ingestion\\n\\nDetails",
            "timestamp": "2026-10-31T10:00:00Z",
            "author": {"name": "Contributor", "email": "contributor@example.com"},
        }],
    }
    response = _send_webhook(client, payload, "push", "push-delivery-1", secret)
    assert response.status_code == 200
    assert response.json()["events_emitted"] == 2
    assert response.json()["outcome"] == "processed"

    duplicate = _send_webhook(client, payload, "push", "push-delivery-1", secret)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True

    generator, db = _db_session()
    try:
        commits = db.query(GitEvent).filter_by(project_id=project_id).all()
        deliveries = db.query(GitHubWebhookDelivery).filter_by(delivery_id="push-delivery-1").all()
        activity = db.query(ActivityEvent).filter_by(project_id=project_id, event_type="github.push").all()
        assert len(commits) == 1
        assert commits[0].branch == "feature/webhooks"
        assert commits[0].author == "Contributor"
        assert len(deliveries) == 1
        assert len(activity) == 1
    finally:
        generator.close()


def test_pull_request_webhook_creates_project_activity(client, monkeypatch):
    project_id = _project_with_repository(client, "pr-webhook@example.com")
    secret = "test-webhook-secret"
    monkeypatch.setattr(config.settings, "github_webhook_secret", secret)
    payload = {
        "action": "opened",
        "repository": {"full_name": "acme/devsync"},
        "sender": {"login": "coder"},
        "pull_request": {
            "number": 42,
            "title": "Add workflow intelligence",
            "state": "open",
            "draft": False,
            "html_url": "https://github.com/acme/devsync/pull/42",
            "head": {"ref": "feature/workflow"},
            "base": {"ref": "main"},
        },
    }
    response = _send_webhook(client, payload, "pull_request", "pr-delivery-1", secret)
    assert response.status_code == 200
    assert response.json()["events_emitted"] == 1

    generator, db = _db_session()
    try:
        event = db.query(ActivityEvent).filter_by(
            project_id=project_id, event_type="github.pull_request.opened"
        ).one()
        details = json.loads(event.payload)
        assert details["number"] == 42
        assert details["head"] == "feature/workflow"
        assert details["base"] == "main"
    finally:
        generator.close()


def test_webhook_acknowledges_unlinked_repository_without_project_data(client, monkeypatch):
    monkeypatch.setattr(config.settings, "github_webhook_secret", "test-webhook-secret")
    response = _send_webhook(
        client, {"repository": {"full_name": "other/unlinked"}, "commits": []},
        "push", "unlinked-delivery-1", "test-webhook-secret"
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"
    assert response.json()["project_id"] is None


def test_duplicate_commit_across_distinct_push_deliveries_is_idempotent(client, monkeypatch):
    project_id = _project_with_repository(client, "duplicate-commit-webhook@example.com")
    secret = "test-webhook-secret"
    monkeypatch.setattr(config.settings, "github_webhook_secret", secret)
    commit_hash = "c" * 40
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "acme/devsync"},
        "commits": [{
            "id": commit_hash,
            "message": "A commit delivered in more than one push payload",
            "timestamp": "2026-10-31T12:00:00Z",
            "author": {"name": "Contributor", "email": "contributor@example.com"},
        }],
    }
    first = _send_webhook(client, payload, "push", "commit-delivery-first", secret)
    second = _send_webhook(client, payload, "push", "commit-delivery-second", secret)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is False

    generator, db = _db_session()
    try:
        commits = db.query(GitEvent).filter_by(
            project_id=project_id, commit_hash=commit_hash
        ).all()
        deliveries = db.query(GitHubWebhookDelivery).filter(
            GitHubWebhookDelivery.delivery_id.in_([
                "commit-delivery-first", "commit-delivery-second"
            ])
        ).all()
        assert len(commits) == 1
        assert len(deliveries) == 2
    finally:
        generator.close()


def test_check_run_and_check_suite_webhooks_create_activity(client, monkeypatch):
    project_id = _project_with_repository(client, "checks-webhook@example.com")
    secret = "test-webhook-secret"
    monkeypatch.setattr(config.settings, "github_webhook_secret", secret)
    common = {"repository": {"full_name": "acme/devsync"}}

    check_run = {
        **common,
        "action": "completed",
        "check_run": {
            "name": "Backend CI",
            "status": "completed",
            "conclusion": "failure",
            "html_url": "https://github.com/acme/devsync/actions/runs/1",
            "head_sha": "d" * 40,
        },
    }
    check_suite = {
        **common,
        "action": "completed",
        "check_suite": {
            "status": "completed",
            "conclusion": "success",
            "head_sha": "e" * 40,
        },
    }
    run_response = _send_webhook(client, check_run, "check_run", "check-run-delivery", secret)
    suite_response = _send_webhook(client, check_suite, "check_suite", "check-suite-delivery", secret)
    assert run_response.status_code == 200, run_response.text
    assert suite_response.status_code == 200, suite_response.text
    assert run_response.json()["events_emitted"] == 1
    assert suite_response.json()["events_emitted"] == 1

    generator, db = _db_session()
    try:
        run_event = db.query(ActivityEvent).filter_by(
            project_id=project_id, event_type="github.check_run"
        ).one()
        suite_event = db.query(ActivityEvent).filter_by(
            project_id=project_id, event_type="github.check_suite"
        ).one()
        assert json.loads(run_event.payload)["conclusion"] == "failure"
        assert json.loads(suite_event.payload)["conclusion"] == "success"
    finally:
        generator.close()


def test_webhook_repository_lookup_does_not_treat_underscore_as_sql_wildcard(client, monkeypatch):
    project_id = _project_with_repository(client, "exact-repository-webhook@example.com")
    generator, db = _db_session()
    try:
        project = db.get(Project, project_id)
        project.github_repo_full_name = "acme/dev_sync"
        db.commit()
    finally:
        generator.close()

    secret = "test-webhook-secret"
    monkeypatch.setattr(config.settings, "github_webhook_secret", secret)
    response = _send_webhook(
        client,
        {"repository": {"full_name": "acme/devXsync"}, "ref": "refs/heads/main", "commits": []},
        "push",
        "repository-wildcard-delivery",
        secret,
    )
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "ignored"
    assert response.json()["project_id"] is None

    generator, db = _db_session()
    try:
        assert db.query(ActivityEvent).filter_by(
            project_id=project_id, event_type="github.push"
        ).count() == 0
    finally:
        generator.close()


def test_webhook_push_commit_is_available_to_commit_task_matching(client, monkeypatch):
    project_id = _project_with_repository(client, "webhook-commit-task-match@example.com")
    headers = {
        "Authorization": "Bearer " + client.post(
            "/api/v1/auth/login",
            data={"username": "webhook-commit-task-match@example.com", "password": "secure-pass-123"},
        ).json()["access_token"]
    }
    task = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={"title": "Implement OAuth token refresh", "description": "Refresh expired OAuth tokens safely."},
    ).json()
    secret = "test-webhook-secret"
    monkeypatch.setattr(config.settings, "github_webhook_secret", secret)
    commit_hash = "f" * 40
    payload = {
        "ref": "refs/heads/feature/oauth-refresh",
        "repository": {"full_name": "acme/devsync"},
        "commits": [{
            "id": commit_hash,
            "message": "Implement OAuth token refresh",
            "timestamp": "2026-10-31T13:00:00Z",
            "author": {"name": "Contributor", "email": "contributor@example.com"},
        }],
    }
    response = _send_webhook(client, payload, "push", "push-task-match-delivery", secret)
    assert response.status_code == 200, response.text

    suggestions = client.get(
        f"/api/v1/projects/{project_id}/intelligence/commit-task-suggestions",
        headers=headers,
    )
    assert suggestions.status_code == 200, suggestions.text
    candidate = next(
        item for item in suggestions.json()["suggestions"]
        if item["commit_hash"] == commit_hash
    )
    assert candidate["candidates"][0]["task_id"] == task["id"]
