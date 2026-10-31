import json
import re
from datetime import datetime
from pathlib import PurePosixPath

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import (
    AIConversation, AIMessage, AIOverride, AIRecommendation, CommitTaskLink,
    DevelopmentEvent, FileChange, GitEvent, HandoverRecord, ProjectMember,
    Task, TaskDependency, User,
)
from app.permissions import require_permission, normalize_role
from app.realtime import manager

router = APIRouter(tags=["development intelligence"])

EVENT_TYPES = {
    "file.created", "file.changed", "file.deleted", "branch.changed",
    "commit.created", "workspace.opened", "task.context_changed",
}
CHANGE_TYPES = {"created", "modified", "deleted", "renamed"}


class EventItem(BaseModel):
    event_type: str = Field(min_length=3, max_length=80)
    payload: dict = Field(default_factory=dict)
    source: str = Field(default="vscode", pattern="^(vscode|web|git|api)$")


class EventBatch(BaseModel):
    events: list[EventItem] = Field(min_length=1, max_length=100)


class DependencyCreate(BaseModel):
    depends_on_task_id: str


class CommitLinkCreate(BaseModel):
    commit_hash: str = Field(min_length=7, max_length=40)
    task_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ConversationCreate(BaseModel):
    role: str = Field(min_length=2, max_length=80)
    title: str = Field(default="New conversation", min_length=1, max_length=180)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=12000)


class RecommendationCreate(BaseModel):
    task_id: str | None = None
    recommendation_type: str = Field(min_length=2, max_length=60)
    proposed_value: str = Field(min_length=1, max_length=120)
    rationale: str = Field(default="", max_length=10000)
    evidence: list[dict] = Field(default_factory=list, max_length=30)


class OverrideCreate(BaseModel):
    decision: str = Field(pattern="^(accepted|rejected|modified)$")
    reason: str = Field(default="", max_length=5000)


class HandoverCreate(BaseModel):
    summary: str = Field(min_length=1, max_length=12000)
    pending_items: list[str] = Field(default_factory=list, max_length=100)
    blockers: list[str] = Field(default_factory=list, max_length=100)


def _safe_relative_path(value: str) -> str:
    path = value.replace("\\", "/").strip()
    parsed = PurePosixPath(path)
    if not path or parsed.is_absolute() or any(part in ("..", "") for part in parsed.parts) or re.match(r"^[A-Za-z]:", path):
        raise HTTPException(status_code=422, detail="File paths must be relative and cannot traverse outside the workspace")
    return str(parsed)


def _conversation_or_404(db: Session, project_id: str, conversation_id: str, user: User):
    conversation = db.scalar(select(AIConversation).where(
        AIConversation.id == conversation_id,
        AIConversation.project_id == project_id,
        AIConversation.user_id == user.id,
    ))
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/projects/{project_id}/intelligence/events", status_code=202)
async def ingest_events(project_id: str, data: EventBatch, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    stored = []
    for item in data.events:
        if item.event_type not in EVENT_TYPES:
            raise HTTPException(status_code=422, detail=f"Unsupported event type: {item.event_type}")
        payload = item.payload
        if item.event_type.startswith("file."):
            path = _safe_relative_path(str(payload.get("path", "")))
            change_type = item.event_type.split(".", 1)[1]
            if change_type not in CHANGE_TYPES:
                change_type = "modified"
            task_id = payload.get("task_id")
            if task_id and not db.scalar(select(Task.id).where(Task.id == task_id, Task.project_id == project_id)):
                raise HTTPException(status_code=422, detail="Referenced task does not belong to this project")
            db.add(FileChange(
                project_id=project_id, actor_id=user.id, path=path,
                change_type=change_type, branch=str(payload.get("branch", ""))[:255],
                commit_hash=str(payload.get("commit_hash", ""))[:40] or None,
                task_id=task_id,
            ))
        event = DevelopmentEvent(
            project_id=project_id, actor_id=user.id, event_type=item.event_type,
            payload=json.dumps(payload, ensure_ascii=False), source=item.source,
        )
        db.add(event)
        stored.append(event)
    record_activity(db, project_id, user.id, "development.events_ingested", {"count": len(stored), "source": "vscode"})
    db.commit()
    for event in stored:
        db.refresh(event)
    await manager.broadcast(project_id, {"type": "development.events", "data": {"count": len(stored)}})
    return {"accepted": len(stored), "event_ids": [event.id for event in stored]}


@router.get("/projects/{project_id}/intelligence/events")
def list_development_events(project_id: str, limit: int = Query(default=100, ge=1, le=500),
                            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    rows = db.scalars(select(DevelopmentEvent).where(
        DevelopmentEvent.project_id == project_id
    ).order_by(DevelopmentEvent.created_at.desc()).limit(limit)).all()
    return [{"id": r.id, "actor_id": r.actor_id, "event_type": r.event_type,
             "payload": json.loads(r.payload), "source": r.source, "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/projects/{project_id}/intelligence/files")
def list_file_changes(project_id: str, limit: int = Query(default=100, ge=1, le=500),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    rows = db.scalars(select(FileChange).where(FileChange.project_id == project_id)
                      .order_by(FileChange.created_at.desc()).limit(limit)).all()
    return [{"id": r.id, "actor_id": r.actor_id, "path": r.path, "change_type": r.change_type,
             "branch": r.branch, "commit_hash": r.commit_hash, "task_id": r.task_id,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/projects/{project_id}/tasks/{task_id}/dependencies", status_code=201)
def add_task_dependency(project_id: str, task_id: str, data: DependencyCreate,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    if task_id == data.depends_on_task_id:
        raise HTTPException(status_code=422, detail="A task cannot depend on itself")
    task = db.scalar(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    dependency = db.scalar(select(Task).where(Task.id == data.depends_on_task_id, Task.project_id == project_id))
    if not task or not dependency:
        raise HTTPException(status_code=404, detail="Both tasks must belong to this project")
    existing = db.scalar(select(TaskDependency).where(
        TaskDependency.project_id == project_id,
        TaskDependency.task_id == task_id,
        TaskDependency.depends_on_task_id == data.depends_on_task_id,
    ))
    if existing:
        return {"id": existing.id, "task_id": task_id, "depends_on_task_id": data.depends_on_task_id}
    # Reject cycles: if the proposed prerequisite already depends (directly or transitively) on task_id.
    edges = db.scalars(select(TaskDependency).where(TaskDependency.project_id == project_id)).all()
    graph: dict[str, list[str]] = {}
    for edge in edges:
        graph.setdefault(edge.task_id, []).append(edge.depends_on_task_id)
    stack, visited = [data.depends_on_task_id], set()
    while stack:
        current = stack.pop()
        if current == task_id:
            raise HTTPException(status_code=409, detail="Dependency would create a cycle")
        if current not in visited:
            visited.add(current)
            stack.extend(graph.get(current, []))
    row = TaskDependency(project_id=project_id, task_id=task_id,
                         depends_on_task_id=data.depends_on_task_id, created_by_id=user.id)
    db.add(row)
    record_activity(db, project_id, user.id, "task.dependency_added",
                    {"task_id": task_id, "depends_on_task_id": data.depends_on_task_id})
    db.commit()
    db.refresh(row)
    return {"id": row.id, "task_id": task_id, "depends_on_task_id": data.depends_on_task_id}


@router.get("/projects/{project_id}/tasks/{task_id}/dependencies")
def list_task_dependencies(project_id: str, task_id: str, db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    if not db.scalar(select(Task.id).where(Task.id == task_id, Task.project_id == project_id)):
        raise HTTPException(status_code=404, detail="Task not found")
    rows = db.scalars(select(TaskDependency).where(
        TaskDependency.project_id == project_id, TaskDependency.task_id == task_id
    )).all()
    return [{"id": r.id, "task_id": r.task_id, "depends_on_task_id": r.depends_on_task_id} for r in rows]


@router.delete("/projects/{project_id}/tasks/{task_id}/dependencies/{dependency_id}", status_code=204)
def delete_task_dependency(project_id: str, task_id: str, dependency_id: str,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    row = db.scalar(select(TaskDependency).where(
        TaskDependency.id == dependency_id, TaskDependency.project_id == project_id,
        TaskDependency.task_id == task_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Dependency not found")
    db.delete(row)
    db.commit()


@router.post("/projects/{project_id}/intelligence/commit-links", status_code=201)
def link_commit_to_task(project_id: str, data: CommitLinkCreate, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    commit = db.scalar(select(GitEvent).where(
        GitEvent.project_id == project_id, GitEvent.commit_hash == data.commit_hash
    ))
    task = db.scalar(select(Task).where(Task.project_id == project_id, Task.id == data.task_id))
    if not commit or not task:
        raise HTTPException(status_code=404, detail="Commit and task must both exist in this project")
    row = db.scalar(select(CommitTaskLink).where(
        CommitTaskLink.project_id == project_id, CommitTaskLink.commit_hash == data.commit_hash,
        CommitTaskLink.task_id == data.task_id,
    ))
    if row:
        row.confidence = data.confidence
    else:
        row = CommitTaskLink(project_id=project_id, commit_hash=data.commit_hash, task_id=data.task_id,
                             linked_by_id=user.id, confidence=data.confidence)
        db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "commit_hash": row.commit_hash, "task_id": row.task_id, "confidence": row.confidence}


@router.get("/projects/{project_id}/intelligence/commit-links")
def list_commit_links(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    rows = db.scalars(select(CommitTaskLink).where(CommitTaskLink.project_id == project_id)
                      .order_by(CommitTaskLink.created_at.desc())).all()
    return [{"id": r.id, "commit_hash": r.commit_hash, "task_id": r.task_id,
             "confidence": r.confidence, "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/projects/{project_id}/ai/conversations", status_code=201)
def create_conversation(project_id: str, data: ConversationCreate, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    role = normalize_role(member.role)
    if data.role != role:
        raise HTTPException(status_code=403, detail="Conversation role must match your assigned project role")
    row = AIConversation(project_id=project_id, user_id=user.id, role=role, title=data.title.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "project_id": row.project_id, "role": row.role, "title": row.title,
            "created_at": row.created_at.isoformat()}


@router.get("/projects/{project_id}/ai/conversations")
def list_conversations(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    rows = db.scalars(select(AIConversation).where(
        AIConversation.project_id == project_id, AIConversation.user_id == user.id
    ).order_by(AIConversation.updated_at.desc())).all()
    return [{"id": r.id, "role": r.role, "title": r.title, "created_at": r.created_at.isoformat(),
             "updated_at": r.updated_at.isoformat()} for r in rows]


@router.get("/projects/{project_id}/ai/conversations/{conversation_id}/messages")
def list_messages(project_id: str, conversation_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    _conversation_or_404(db, project_id, conversation_id, user)
    rows = db.scalars(select(AIMessage).where(AIMessage.conversation_id == conversation_id)
                      .order_by(AIMessage.created_at.asc())).all()
    return [{"id": r.id, "sender": r.sender, "content": r.content, "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/projects/{project_id}/ai/conversations/{conversation_id}/messages", status_code=201)
async def send_message(project_id: str, conversation_id: str, data: MessageCreate,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conversation = _conversation_or_404(db, project_id, conversation_id, user)
    project, member = get_project_member(project_id, db, user)
    if conversation.role != normalize_role(member.role):
        raise HTTPException(status_code=403, detail="Your project role changed; create a new conversation")
    user_message = AIMessage(conversation_id=conversation_id, sender="user", content=data.content.strip())
    db.add(user_message)
    conversation.updated_at = datetime.utcnow()
    db.commit()
    history = db.scalars(select(AIMessage).where(AIMessage.conversation_id == conversation_id)
                         .order_by(AIMessage.created_at.desc()).limit(12)).all()
    history.reverse()
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Chat message was saved, but Gemini is not configured")
    tasks = db.scalars(select(Task).where(Task.project_id == project_id)
                       .order_by(Task.updated_at.desc()).limit(30)).all()
    prompt = (
        f"You are DevSync AI assisting a {conversation.role}. Use only supplied project facts; "
        f"do not invent code or events. Project: {project.name}. Description: {project.description}. "
        f"Tasks: {json.dumps([{'id': t.id, 'title': t.title, 'status': t.status.value} for t in tasks])}. "
        f"Conversation: {json.dumps([{'role': 'user' if m.sender == 'user' else 'model', 'text': m.content} for m in history])}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, params={"key": settings.gemini_api_key},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}})
        response.raise_for_status()
        answer = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Message saved, but Gemini did not return a valid response") from exc
    assistant_message = AIMessage(conversation_id=conversation_id, sender="assistant", content=answer)
    db.add(assistant_message)
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assistant_message)
    return {"id": assistant_message.id, "sender": "assistant", "content": answer,
            "created_at": assistant_message.created_at.isoformat()}


@router.delete("/projects/{project_id}/ai/conversations/{conversation_id}", status_code=204)
def delete_conversation(project_id: str, conversation_id: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    conversation = _conversation_or_404(db, project_id, conversation_id, user)
    db.delete(conversation)
    db.commit()


@router.post("/projects/{project_id}/ai/recommendations", status_code=201)
def create_recommendation(project_id: str, data: RecommendationCreate, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    if data.task_id and not db.scalar(select(Task.id).where(Task.id == data.task_id, Task.project_id == project_id)):
        raise HTTPException(status_code=404, detail="Task not found in this project")
    row = AIRecommendation(project_id=project_id, task_id=data.task_id, created_by_id=user.id,
        recommendation_type=data.recommendation_type, proposed_value=data.proposed_value,
        rationale=data.rationale, evidence=json.dumps(data.evidence, ensure_ascii=False))
    db.add(row)
    record_activity(db, project_id, user.id, "ai.recommendation_created",
                    {"recommendation_type": data.recommendation_type, "task_id": data.task_id})
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status, "recommendation_type": row.recommendation_type,
            "proposed_value": row.proposed_value, "rationale": row.rationale,
            "evidence": json.loads(row.evidence), "task_id": row.task_id}


@router.get("/projects/{project_id}/ai/recommendations")
def list_recommendations(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    rows = db.scalars(select(AIRecommendation).where(AIRecommendation.project_id == project_id)
                      .order_by(AIRecommendation.created_at.desc()).limit(200)).all()
    return [{"id": r.id, "task_id": r.task_id, "recommendation_type": r.recommendation_type,
             "proposed_value": r.proposed_value, "rationale": r.rationale, "evidence": json.loads(r.evidence),
             "status": r.status, "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/projects/{project_id}/ai/recommendations/{recommendation_id}/override")
def override_recommendation(project_id: str, recommendation_id: str, data: OverrideCreate,
                            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    row = db.scalar(select(AIRecommendation).where(
        AIRecommendation.id == recommendation_id, AIRecommendation.project_id == project_id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Recommendation has already been decided")
    row.status = data.decision
    override = AIOverride(recommendation_id=row.id, user_id=user.id, decision=data.decision, reason=data.reason)
    db.add(override)
    record_activity(db, project_id, user.id, "ai.recommendation_overridden",
                    {"recommendation_id": row.id, "decision": data.decision})
    db.commit()
    return {"recommendation_id": row.id, "status": row.status, "decision": data.decision}


@router.post("/projects/{project_id}/handover", status_code=201)
def create_handover(project_id: str, data: HandoverCreate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    row = HandoverRecord(project_id=project_id, user_id=user.id, summary=data.summary.strip(),
                         pending_items=json.dumps(data.pending_items), blockers=json.dumps(data.blockers))
    db.add(row)
    record_activity(db, project_id, user.id, "developer.handover_created", {"handover_id": row.id})
    db.commit()
    db.refresh(row)
    return {"id": row.id, "summary": row.summary, "pending_items": data.pending_items,
            "blockers": data.blockers, "created_at": row.created_at.isoformat()}


@router.get("/projects/{project_id}/handover")
def list_handovers(project_id: str, limit: int = Query(default=50, ge=1, le=200),
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    rows = db.scalars(select(HandoverRecord).where(HandoverRecord.project_id == project_id)
                      .order_by(HandoverRecord.created_at.desc()).limit(limit)).all()
    return [{"id": r.id, "user_id": r.user_id, "summary": r.summary,
             "pending_items": json.loads(r.pending_items), "blockers": json.loads(r.blockers),
             "created_at": r.created_at.isoformat()} for r in rows]
