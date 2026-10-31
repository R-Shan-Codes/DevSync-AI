import json
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member
from app.models import ActivityEvent, BugReport, CodeReview, GitEvent, HandoverRecord, Task, TestRun, User

router = APIRouter(prefix="/projects/{project_id}/memory", tags=["project memory"])


@router.get("")
def project_memory(project_id: str, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    limit = max(1, min(limit, 200))
    events = db.scalars(select(ActivityEvent).where(ActivityEvent.project_id == project_id).order_by(ActivityEvent.created_at.desc()).limit(limit)).all()
    tasks = db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.updated_at.desc()).limit(50)).all()
    commits = db.scalars(select(GitEvent).where(GitEvent.project_id == project_id).order_by(GitEvent.created_at.desc()).limit(20)).all()
    reviews = db.scalars(select(CodeReview).where(CodeReview.project_id == project_id).order_by(CodeReview.created_at.desc()).limit(20)).all()
    tests = db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc()).limit(20)).all()
    bugs = db.scalars(select(BugReport).where(BugReport.project_id == project_id, BugReport.status == "open").order_by(BugReport.updated_at.desc()).limit(20)).all()
    handovers = db.scalars(select(HandoverRecord).where(HandoverRecord.project_id == project_id).order_by(HandoverRecord.created_at.desc()).limit(20)).all()
    return {
      "tasks": [{"id": t.id, "title": t.title, "status": t.status.value, "assignee_id": t.assignee_id, "updated_at": t.updated_at.isoformat()} for t in tasks],
      "recent_activity": [{"type": e.event_type, "payload": json.loads(e.payload), "created_at": e.created_at.isoformat()} for e in events],
      "recent_commits": [{"hash": c.commit_hash, "branch": c.branch, "message": c.message, "author": c.author, "created_at": c.created_at.isoformat()} for c in commits],
      "recent_reviews": [{"task_id": r.task_id, "decision": r.decision, "summary": r.summary, "created_at": r.created_at.isoformat()} for r in reviews],
      "recent_test_runs": [{"task_id": t.task_id, "result": t.result, "total": t.total, "passed": t.passed, "failed": t.failed, "created_at": t.created_at.isoformat()} for t in tests],
      "open_bugs": [{"id": b.id, "task_id": b.task_id, "title": b.title, "severity": b.severity, "status": b.status, "updated_at": b.updated_at.isoformat()} for b in bugs],
      "recent_handovers": [{"id": h.id, "user_id": h.user_id, "summary": h.summary, "pending_items": json.loads(h.pending_items), "blockers": json.loads(h.blockers), "created_at": h.created_at.isoformat()} for h in handovers],
    }
