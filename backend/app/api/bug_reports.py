from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import BugReport, Task, User
from app.permissions import require_permission
from app.realtime import manager
from app.schemas import BugReportCreate, BugReportRead, BugReportUpdate

router = APIRouter(prefix="/projects/{project_id}/bugs", tags=["bugs"])

@router.post("", response_model=BugReportRead, status_code=201)
async def create_bug(project_id: str, data: BugReportCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "edit")
    task = db.scalar(select(Task).where(Task.id == data.task_id, Task.project_id == project_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found in this project")
    bug = BugReport(project_id=project_id, task_id=data.task_id, reporter_id=user.id, title=data.title.strip(), description=data.description.strip(), severity=data.severity)
    db.add(bug)
    record_activity(db, project_id, user.id, "bug.created", {"task_id": data.task_id, "title": bug.title, "severity": bug.severity})
    db.commit()
    db.refresh(bug)
    await manager.broadcast(project_id, {"type": "bug.created", "data": {"id": bug.id, "task_id": bug.task_id, "title": bug.title, "severity": bug.severity}})
    return bug

@router.get("", response_model=list[BugReportRead])
def list_bugs(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    return db.scalars(select(BugReport).where(BugReport.project_id == project_id).order_by(BugReport.created_at.desc())).all()

@router.patch("/{bug_id}", response_model=BugReportRead)
async def update_bug(project_id: str, bug_id: str, data: BugReportUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    require_permission(member, "review")
    bug = db.scalar(select(BugReport).where(BugReport.id == bug_id, BugReport.project_id == project_id))
    if not bug:
        raise HTTPException(status_code=404, detail="Bug report not found")
    previous = bug.status
    bug.status = data.status
    record_activity(db, project_id, user.id, "bug.status_changed", {"bug_id": bug.id, "from": previous, "to": bug.status})
    db.commit()
    db.refresh(bug)
    await manager.broadcast(project_id, {"type": "bug.updated", "data": {"id": bug.id, "status": bug.status}})
    return bug
