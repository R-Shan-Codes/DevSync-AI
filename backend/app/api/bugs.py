import json
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import BugAnalysis, BugReport, CommitTaskLink, FileChange, GitEvent, Task, TaskDependency, User
from app.permissions import require_permission
from app.realtime import manager

router = APIRouter(prefix="/projects/{project_id}/bugs", tags=["bug intelligence"])


class BugCreate(BaseModel):
    task_id: str
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=12000)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


class BugUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|in_progress|resolved|closed)$")
    resolution: str | None = Field(default=None, max_length=12000)


@router.post("", status_code=201)
async def create_bug(project_id: str, data: BugCreate, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    task = db.scalar(select(Task).where(Task.id == data.task_id, Task.project_id == project_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found in this project")
    bug = BugReport(project_id=project_id, task_id=task.id, reporter_id=user.id,
                    title=data.title.strip(), description=data.description.strip(), severity=data.severity)
    db.add(bug)
    record_activity(db, project_id, user.id, "bug.created",
                    {"title": bug.title, "task_id": task.id, "severity": bug.severity})
    db.commit()
    db.refresh(bug)
    await manager.broadcast(project_id, {"type": "bug.created", "data": {"id": bug.id, "task_id": task.id}})
    return {"id": bug.id, "project_id": bug.project_id, "task_id": bug.task_id,
            "reporter_id": bug.reporter_id, "title": bug.title, "description": bug.description,
            "severity": bug.severity, "status": bug.status, "resolution": bug.resolution,
            "created_at": bug.created_at.isoformat()}


@router.get("")
def list_bugs(project_id: str, status: str | None = Query(default=None, pattern="^(open|in_progress|resolved|closed)$"),
              limit: int = Query(default=100, ge=1, le=300), db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    query = select(BugReport).where(BugReport.project_id == project_id)
    if status:
        query = query.where(BugReport.status == status)
    rows = db.scalars(query.order_by(BugReport.created_at.desc()).limit(limit)).all()
    return [{"id": b.id, "task_id": b.task_id, "reporter_id": b.reporter_id, "title": b.title,
             "description": b.description, "severity": b.severity, "status": b.status,
             "resolution": b.resolution, "created_at": b.created_at.isoformat(),
             "updated_at": b.updated_at.isoformat()} for b in rows]


@router.patch("/{bug_id}")
async def update_bug(project_id: str, bug_id: str, data: BugUpdate, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    bug = db.scalar(select(BugReport).where(BugReport.id == bug_id, BugReport.project_id == project_id))
    if not bug:
        raise HTTPException(status_code=404, detail="Bug report not found")
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None:
            setattr(bug, key, value)
    record_activity(db, project_id, user.id, "bug.updated", {"bug_id": bug.id, "status": bug.status})
    db.commit()
    db.refresh(bug)
    await manager.broadcast(project_id, {"type": "bug.updated", "data": {"id": bug.id, "status": bug.status}})
    return {"id": bug.id, "status": bug.status, "resolution": bug.resolution}


@router.post("/{bug_id}/analyze-impact", status_code=201)
def analyze_bug_impact(project_id: str, bug_id: str, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "view")
    bug = db.scalar(select(BugReport).where(BugReport.id == bug_id, BugReport.project_id == project_id))
    if not bug:
        raise HTTPException(status_code=404, detail="Bug report not found")

    dependencies = db.scalars(select(TaskDependency).where(TaskDependency.project_id == project_id)).all()
    downstream: dict[str, list[str]] = {}
    for edge in dependencies:
        downstream.setdefault(edge.depends_on_task_id, []).append(edge.task_id)

    # Follow only downstream dependencies, with a depth bound to keep analysis predictable.
    depths = {bug.task_id: 0}
    queue = deque([bug.task_id])
    while queue:
        current = queue.popleft()
        if depths[current] >= 3:
            continue
        for child in downstream.get(current, []):
            if child not in depths:
                depths[child] = depths[current] + 1
                queue.append(child)

    impacted_ids = list(depths)
    tasks = db.scalars(select(Task).where(Task.project_id == project_id, Task.id.in_(impacted_ids))).all()
    task_by_id = {task.id: task for task in tasks}
    direct_links = db.scalars(select(CommitTaskLink).where(
        CommitTaskLink.project_id == project_id, CommitTaskLink.task_id == bug.task_id
    )).all()
    commit_hashes = [link.commit_hash for link in direct_links]
    commits = db.scalars(select(GitEvent).where(
        GitEvent.project_id == project_id, GitEvent.commit_hash.in_(commit_hashes)
    )).all() if commit_hashes else []
    direct_files = db.scalars(select(FileChange).where(
        FileChange.project_id == project_id, FileChange.task_id == bug.task_id
    )).all()
    direct_paths = {item.path for item in direct_files}
    related_files = db.scalars(select(FileChange).where(
        FileChange.project_id == project_id, FileChange.path.in_(direct_paths)
    )).all() if direct_paths else []
    shared_by_task: dict[str, set[str]] = {}
    for item in related_files:
        if item.task_id and item.task_id != bug.task_id:
            shared_by_task.setdefault(item.task_id, set()).add(item.path)

    impacts = []
    for task_id, depth in depths.items():
        task = task_by_id.get(task_id)
        if not task:
            continue
        evidence = []
        if task_id == bug.task_id:
            evidence.append({"type": "reported_task", "detail": "Bug was reported against this task"})
        else:
            evidence.append({"type": "dependency_chain", "depth": depth,
                             "detail": "Task depends directly or transitively on the bug's task"})
        if shared_by_task.get(task_id):
            evidence.append({"type": "shared_files", "paths": sorted(shared_by_task[task_id])})
        impacts.append({
            "task_id": task.id, "title": task.title, "status": task.status.value,
            "assignee_id": task.assignee_id, "dependency_depth": depth,
            "confidence": 1.0 if depth == 0 else max(0.55, 0.85 - depth * 0.1),
            "evidence": evidence,
        })

    summary = (
        f"Found {len(impacts)} task(s) in the reported task's downstream dependency chain. "
        f"Found {len(commits)} explicitly linked commit(s) and {len(direct_paths)} changed file(s). "
        "These are impact candidates, not confirmed root causes or developer fault."
    )
    analysis = BugAnalysis(project_id=project_id, bug_id=bug.id, analyzer_id=user.id,
                           summary=summary, impacts=json.dumps(impacts, ensure_ascii=False))
    db.add(analysis)
    record_activity(db, project_id, user.id, "bug.impact_analyzed",
                    {"bug_id": bug.id, "impacted_task_count": len(impacts), "linked_commit_count": len(commits)})
    db.commit()
    db.refresh(analysis)
    return {
        "analysis_id": analysis.id, "bug_id": bug.id, "summary": summary, "impacts": impacts,
        "candidate_commits": [{"commit_hash": commit.commit_hash, "author": commit.author,
                               "author_email": commit.author_email, "message": commit.message}
                              for commit in commits],
        "changed_files": sorted(direct_paths),
        "warning": "Impact candidates are evidence-based leads, not confirmed root causes. No task status was changed.",
    }


@router.get("/{bug_id}/analyses")
def list_bug_analyses(project_id: str, bug_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    bug = db.scalar(select(BugReport).where(BugReport.id == bug_id, BugReport.project_id == project_id))
    if not bug:
        raise HTTPException(status_code=404, detail="Bug report not found")
    rows = db.scalars(select(BugAnalysis).where(
        BugAnalysis.project_id == project_id, BugAnalysis.bug_id == bug_id
    ).order_by(BugAnalysis.created_at.desc())).all()
    return [{"id": row.id, "summary": row.summary, "impacts": json.loads(row.impacts),
             "created_at": row.created_at.isoformat()} for row in rows]
