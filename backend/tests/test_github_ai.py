import asyncio
import io
import json
import zipfile

import httpx

from app.core.database import get_db
from app.main import app
from app.models import AIReviewArtifact, Project, User
from app.api.github_ai import extract_job_logs, github_download_bounded, normalize_findings, parse_ai_json, redact_secrets


def register(client, email):
    client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "AI Review Tester", "password": "secure-pass-123"
    })
    token = client.post("/api/v1/auth/login", data={
        "username": email, "password": "secure-pass-123"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_ai_github_helpers_parse_and_normalize_untrusted_output():
    parsed = parse_ai_json(' ```json\n{"summary":"One issue","findings":[]}\n``` ')
    assert parsed["summary"] == "One issue"
    findings = normalize_findings([{
        "severity": "SEVERE",
        "title": "Possible bug",
        "line": -4,
        "confidence": 5,
        "explanation": "Evidence",
    }])
    assert findings[0]["severity"] == "info"
    assert findings[0]["line"] is None
    assert findings[0]["confidence"] == 1.0


def test_ai_github_redacts_common_credentials():
    value = "token=supersecretvalue ghp_abcdefghijklmnopqrstuvwxyz1234567890 AKIA1234567890ABCDEF"
    redacted = redact_secrets(value)
    assert "supersecretvalue" not in redacted
    assert "ghp_abcdefghijklmnopqrstuvwxyz1234567890" not in redacted
    assert "AKIA1234567890ABCDEF" not in redacted


def test_ai_github_analysis_requires_project_and_valid_commit_sha(client):
    headers = register(client, "github-ai-validation@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "AI GitHub Project"}).json()
    response = client.post(
        f"/api/v1/github/projects/{project['id']}/checks/not-a-sha/analyze",
        headers=headers,
    )
    assert response.status_code == 422


def test_ai_github_review_requires_connected_github_account(client):
    headers = register(client, "github-ai-account@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "AI GitHub Project"}).json()
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
    response = client.post(
        f"/api/v1/github/projects/{project['id']}/pull-requests/12/review",
        headers=headers,
    )
    assert response.status_code == 409
    assert "Connect your GitHub account" in response.json()["detail"]


def test_ai_github_analysis_history_is_project_scoped(client):
    headers = register(client, "github-ai-history@example.com")
    first = client.post("/api/v1/projects", headers=headers, json={"name": "First AI Project"}).json()
    second = client.post("/api/v1/projects", headers=headers, json={"name": "Second AI Project"}).json()

    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        db.add(AIReviewArtifact(
            project_id=first["id"],
            requester_id=db.query(User).filter_by(email="github-ai-history@example.com").one().id,
            artifact_type="pull_request_review",
            source_key="pr:8",
            summary="One potential issue.",
            findings=json.dumps([{"severity": "medium", "title": "Check edge case"}]),
        ))
        db.commit()
    finally:
        generator.close()

    first_history = client.get(
        f"/api/v1/github/projects/{first['id']}/ai-analyses", headers=headers
    )
    second_history = client.get(
        f"/api/v1/github/projects/{second['id']}/ai-analyses", headers=headers
    )
    assert first_history.status_code == 200
    assert len(first_history.json()) == 1
    assert first_history.json()[0]["source_key"] == "pr:8"
    assert second_history.status_code == 200
    assert second_history.json() == []


def test_ai_github_analysis_can_be_explicitly_linked_to_task(client):
    headers = register(client, "github-ai-task-link@example.com")
    project = client.post("/api/v1/projects", headers=headers, json={"name": "AI Task Link"}).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        headers=headers,
        json={"title": "Fix authentication token refresh"},
    ).json()

    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        user = db.query(User).filter_by(email="github-ai-task-link@example.com").one()
        artifact = AIReviewArtifact(
            project_id=project["id"],
            requester_id=user.id,
            artifact_type="pull_request_review",
            source_key="pr:42",
            summary="Potential token refresh race condition.",
            findings=json.dumps([{"severity": "high", "title": "Refresh token race"}]),
        )
        db.add(artifact)
        db.commit()
        artifact_id = artifact.id
    finally:
        generator.close()

    linked = client.post(
        f"/api/v1/github/projects/{project['id']}/ai-analyses/{artifact_id}/tasks",
        headers=headers,
        json={"task_id": task["id"]},
    )
    assert linked.status_code == 201, linked.text
    assert linked.json()["created"] is True

    duplicate = client.post(
        f"/api/v1/github/projects/{project['id']}/ai-analyses/{artifact_id}/tasks",
        headers=headers,
        json={"task_id": task["id"]},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["created"] is False

    listed = client.get(
        f"/api/v1/github/projects/{project['id']}/ai-analyses/{artifact_id}/tasks",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["task_id"] == task["id"]
    assert listed.json()[0]["task_title"] == task["title"]


def test_ai_github_task_link_rejects_foreign_project_task(client):
    owner = register(client, "github-ai-link-owner@example.com")
    outsider = register(client, "github-ai-link-outsider@example.com")
    project = client.post("/api/v1/projects", headers=owner, json={"name": "Owned project"}).json()
    foreign_project = client.post("/api/v1/projects", headers=outsider, json={"name": "Foreign project"}).json()
    foreign_task = client.post(
        f"/api/v1/projects/{foreign_project['id']}/tasks",
        headers=outsider,
        json={"title": "Foreign task"},
    ).json()

    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        user = db.query(User).filter_by(email="github-ai-link-owner@example.com").one()
        artifact = AIReviewArtifact(
            project_id=project["id"],
            requester_id=user.id,
            artifact_type="ci_failure_analysis",
            source_key="commit:" + "a" * 40,
            summary="CI failed.",
            findings="[]",
        )
        db.add(artifact)
        db.commit()
        artifact_id = artifact.id
    finally:
        generator.close()

    response = client.post(
        f"/api/v1/github/projects/{project['id']}/ai-analyses/{artifact_id}/tasks",
        headers=owner,
        json={"task_id": foreign_task["id"]},
    )
    assert response.status_code == 404


def test_ai_github_redacts_bearer_jwt_slack_and_npm_tokens():
    value = (
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456 "
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturevalue123456 "
        "xoxb-1234567890-abcdefghijk npm_abcdefghijklmnopqrstuvwxyz123456"
    )
    redacted = redact_secrets(value)
    assert "abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted
    assert "xoxb-1234567890-abcdefghijk" not in redacted
    assert "npm_abcdefghijklmnopqrstuvwxyz123456" not in redacted


def test_github_job_log_extraction_is_bounded_and_ignores_non_log_files():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("logs/step.txt", "First failure: assertion mismatch")
        zipped.writestr("logs/binary.bin", "should not be included")
    result = extract_job_logs(archive.getvalue())
    assert "First failure: assertion mismatch" in result
    assert "should not be included" not in result


def test_github_job_log_extraction_rejects_oversized_and_invalid_archives():
    assert "10 MB safety limit" in extract_job_logs(b"x" * 10_000_001)
    assert "could not be decoded safely" in extract_job_logs(b"not a zip archive")


def test_github_log_download_stream_enforces_body_limit():
    async def run():
        async def too_large(request):
            return httpx.Response(200, content=b"123456", headers={"content-length": "6"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(too_large)) as client:
            try:
                await github_download_bounded(client, "https://api.github.test/logs", "token", 5)
            except Exception as exc:
                assert getattr(exc, "status_code", None) == 413
            else:
                raise AssertionError("Expected the archive size limit to reject the response")

    asyncio.run(run())


def test_github_log_download_stream_reads_valid_bounded_body():
    async def run():
        async def response(request):
            return httpx.Response(200, content=b"small log")

        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            result = await github_download_bounded(
                client, "https://api.github.test/logs", "token", 100
            )
            assert result == b"small log"

    asyncio.run(run())
