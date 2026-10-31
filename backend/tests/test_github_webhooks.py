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
