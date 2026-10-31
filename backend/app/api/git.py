import json
import subprocess
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import GitEvent, ProjectRole, User
from app.realtime import manager
from app.permissions import require_permission
from app.schemas import GitSyncRequest, GitEventRead

router = APIRouter(prefix="/projects/{project_id}/git", tags=["git"])

def resolve_repository(relative_path: str) -> Path:
    root = Path(settings.workspace_root).resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Repository path must be inside WORKSPACE_ROOT")
    if not (candidate / ".git").exists():
        raise HTTPException(status_code=400, detail="No Git repository found at the supplied path")
    return candidate

def run_git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=503, detail=f"Git command failed: {exc}") from exc
    if result.returncode:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "Git command failed")
    return result.stdout.strip()

@router.post("/sync", response_model=list[GitEventRead])
async def sync_git(project_id: str, data: GitSyncRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, 'view')
    repo = resolve_repository(data.repository_path)
    branch = run_git(repo, "branch", "--show-current")
    status = run_git(repo, "status", "--porcelain")
    log = run_git(repo, "log", "-n", str(data.commit_limit), "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%s")
    created = []
    for line in filter(None, log.splitlines()):
        parts = line.split("\x1f", 4)
        if len(parts) != 5:
            continue
        commit_hash, author, email, committed_at, message = parts
        existing = db.scalar(select(GitEvent).where(GitEvent.project_id == project_id, GitEvent.commit_hash == commit_hash))
        if existing:
            continue
        event = GitEvent(project_id=project_id, actor_id=user.id, repository_path=data.repository_path, branch=branch,
                         commit_hash=commit_hash, author=author, author_email=email, committed_at=committed_at, message=message)
        db.add(event)
        created.append(event)
    record_activity(db, project_id, user.id, "git.synced", {"branch": branch, "new_commits": len(created), "working_tree_dirty": bool(status)})
    db.commit()
    for event in created:
        db.refresh(event)
        await manager.broadcast(project_id, {"type": "git.commit", "data": {"id": event.id, "branch": branch, "commit_hash": event.commit_hash, "message": event.message, "author": event.author}})
    await manager.broadcast(project_id, {"type": "git.sync", "data": {"branch": branch, "new_commits": len(created), "working_tree_dirty": bool(status)}})
    return created

@router.get("/status")
def git_status(project_id: str, repository_path: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    repo = resolve_repository(repository_path)
    branch = run_git(repo, "branch", "--show-current")
    raw = run_git(repo, "status", "--porcelain")
    return {"branch": branch, "clean": not bool(raw), "changes": [{"status": row[:2], "path": row[3:]} for row in raw.splitlines()], "last_commit": run_git(repo, "rev-parse", "HEAD")}

@router.get("/events", response_model=list[GitEventRead])
def git_events(project_id: str, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    return db.scalars(select(GitEvent).where(GitEvent.project_id == project_id).order_by(GitEvent.created_at.desc()).limit(limit)).all()
