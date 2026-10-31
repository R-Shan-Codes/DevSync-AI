import hashlib
import hmac
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import ActivityEvent, GitEvent, GitHubWebhookDelivery, Project
from app.realtime import manager

router = APIRouter(prefix="/github", tags=["GitHub webhooks"])


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _record_push(db: Session, project: Project, payload: dict) -> list[dict]:
    ref = str(payload.get("ref") or "")
    branch = ref.removeprefix("refs/heads/")[:255] or "unknown"
    repository = project.github_repo_full_name or ""
    sender = payload.get("sender") or {}
    if not isinstance(sender, dict):
        sender = {}
    created_events = []
    commits = payload.get("commits") or []
    if not isinstance(commits, list):
        commits = []
    for commit in commits:
        if not isinstance(commit, dict):
            continue
        commit_hash = str(commit.get("id") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit_hash) or db.scalar(select(GitEvent.id).where(
            GitEvent.project_id == project.id, GitEvent.commit_hash == commit_hash
        )):
            continue
        raw_author = commit.get("author") or {}
        github_author = commit.get("committer") or {}
        if not isinstance(raw_author, dict):
            raw_author = {}
        if not isinstance(github_author, dict):
            github_author = {}
        event = GitEvent(
            project_id=project.id,
            actor_id=project.owner_id,
            repository_path="github:" + repository,
            branch=branch,
            commit_hash=commit_hash,
            author=str(raw_author.get("name") or github_author.get("name") or "Unknown")[:255],
            author_email=str(raw_author.get("email") or "")[:320],
            committed_at=str((commit.get("timestamp") or ""))[:40],
            message=(str(commit.get("message") or "").splitlines() or [""])[0][:1000],
        )
        try:
            # A different delivery can contain a commit already persisted by a
            # concurrent push. Isolate the unique-commit race so the delivery
            # itself can still be recorded and acknowledged.
            with db.begin_nested():
                db.add(event)
                db.flush()
        except IntegrityError:
            continue
        created_events.append({
            "type": "git.commit",
            "data": {
                "branch": branch,
                "commit_hash": commit_hash,
                "message": event.message,
                "author": event.author,
            },
        })
    db.add(ActivityEvent(
        project_id=project.id,
        actor_id=project.owner_id,
        event_type="github.push",
        payload=json.dumps({
            "repository": repository,
            "branch": branch,
            "before": str(payload.get("before") or "")[:40],
            "after": str(payload.get("after") or "")[:40],
            "commits_received": len(payload.get("commits") or []),
            "new_commits": len(created_events),
            "sender": str(sender.get("login") or "unknown")[:100],
        }),
    ))
    created_events.append({
        "type": "github.push",
        "data": {"repository": repository, "branch": branch, "new_commits": len(created_events)},
    })
    return created_events


def _record_pull_request(db: Session, project: Project, action: str, payload: dict) -> dict:
    pull_request = payload.get("pull_request") or {}
    sender = payload.get("sender") or {}
    if not isinstance(pull_request, dict):
        pull_request = {}
    if not isinstance(sender, dict):
        sender = {}
    details = {
        "repository": project.github_repo_full_name,
        "action": action,
        "number": pull_request.get("number"),
        "title": str(pull_request.get("title") or "")[:500],
        "state": pull_request.get("state"),
        "draft": bool(pull_request.get("draft", False)),
        "url": pull_request.get("html_url"),
        "head": ((pull_request.get("head") or {}).get("ref") or "")[:255],
        "base": ((pull_request.get("base") or {}).get("ref") or "")[:255],
        "sender": str(sender.get("login") or "unknown")[:100],
    }
    db.add(ActivityEvent(
        project_id=project.id,
        actor_id=project.owner_id,
        event_type="github.pull_request." + (action or "updated"),
        payload=json.dumps(details),
    ))
    return {"type": "github.pull_request", "data": details}


@router.post("/webhooks")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    secret = settings.github_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="GitHub webhook integration is not configured.")
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > 2_000_000:
        raise HTTPException(status_code=413, detail="Webhook payload exceeds the 2 MB limit.")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 2_000_000:
            raise HTTPException(status_code=413, detail="Webhook payload exceeds the 2 MB limit.")
        chunks.append(chunk)
    body = b"".join(chunks)
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature.")

    delivery_id = request.headers.get("X-GitHub-Delivery", "").strip()
    event_type = request.headers.get("X-GitHub-Event", "").strip().lower()
    if not delivery_id or len(delivery_id) > 100 or not event_type:
        raise HTTPException(status_code=400, detail="Missing or invalid GitHub delivery headers.")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Expected an object")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Webhook body must be a valid JSON object.") from exc

    existing = db.scalar(select(GitHubWebhookDelivery).where(
        GitHubWebhookDelivery.delivery_id == delivery_id
    ))
    if existing:
        return {"accepted": True, "duplicate": True, "outcome": existing.outcome}

    repository = payload.get("repository") or {}
    if not isinstance(repository, dict):
        repository = {}
    repository_full_name = str(repository.get("full_name") or "")[:255]
    project = db.scalar(select(Project).where(
        func.lower(Project.github_repo_full_name) == repository_full_name.lower()
    )) if repository_full_name else None
    action = str(payload.get("action") or "")[:80]
    delivery = GitHubWebhookDelivery(
        delivery_id=delivery_id,
        event_type=event_type[:80],
        action=action,
        repository_full_name=repository_full_name,
        project_id=project.id if project else None,
        payload_sha256=hashlib.sha256(body).hexdigest(),
        outcome="ignored" if not project or event_type not in {"push", "pull_request", "check_run", "check_suite"} else "processed",
    )
    db.add(delivery)

    outbound = []
    if project and event_type == "push":
        outbound = _record_push(db, project, payload)
    elif project and event_type == "pull_request":
        outbound = [_record_pull_request(db, project, action, payload)]
    elif project and event_type in {"check_run", "check_suite"}:
        check = payload.get("check_run") or payload.get("check_suite") or {}
        if not isinstance(check, dict):
            check = {}
        sender = payload.get("sender") or {}
        if not isinstance(sender, dict):
            sender = {}
        details = {
            "repository": repository_full_name,
            "event": event_type,
            "action": action,
            "name": str(check.get("name") or "")[:255],
            "status": check.get("status"),
            "conclusion": check.get("conclusion"),
            "html_url": check.get("html_url"),
            "head_sha": str(check.get("head_sha") or "")[:40],
            "sender": str(sender.get("login") or "unknown")[:100],
        }
        db.add(ActivityEvent(
            project_id=project.id,
            actor_id=project.owner_id,
            event_type="github." + event_type,
            payload=json.dumps(details),
        ))
        outbound = [{"type": "github.check", "data": details}]

    try:
        db.commit()
    except IntegrityError:
        # GitHub may retry or concurrently deliver the same delivery. The
        # unique delivery ID is the final idempotency guard at the database.
        db.rollback()
        duplicate = db.scalar(select(GitHubWebhookDelivery).where(
            GitHubWebhookDelivery.delivery_id == delivery_id
        ))
        if duplicate:
            return {"accepted": True, "duplicate": True, "outcome": duplicate.outcome}
        raise
    if project:
        for event in outbound:
            await manager.broadcast(project.id, event)
    return {
        "accepted": True,
        "duplicate": False,
        "outcome": delivery.outcome,
        "project_id": project.id if project else None,
        "events_emitted": len(outbound),
    }
