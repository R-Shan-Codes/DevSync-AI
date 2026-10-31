from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import CodeReview, ProjectRole, Task, User
from app.realtime import manager
from app.schemas import ReviewCreate, ReviewRead

router = APIRouter(prefix="/projects/{project_id}/reviews", tags=["reviews"])

@router.post("", response_model=ReviewRead, status_code=201)
async def create_review(project_id: str, data: ReviewCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    if member.role not in {ProjectRole.debugger, ProjectRole.administrator}:
        raise HTTPException(status_code=403, detail="Debugger or administrator role required")
    if not db.scalar(select(Task).where(Task.id == data.task_id, Task.project_id == project_id)):
        raise HTTPException(status_code=404, detail="Task not found in this project")
    review = CodeReview(project_id=project_id, task_id=data.task_id, reviewer_id=user.id, decision=data.decision, summary=data.summary, findings=data.findings)
    db.add(review)
    record_activity(db, project_id, user.id, "review.created", {"task_id": data.task_id, "decision": data.decision})
    db.commit()
    db.refresh(review)
    await manager.broadcast(project_id, {"type": "review.created", "data": {"id": review.id, "task_id": review.task_id, "decision": review.decision}})
    return review

@router.get("", response_model=list[ReviewRead])
def list_reviews(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    return db.scalars(select(CodeReview).where(CodeReview.project_id == project_id).order_by(CodeReview.created_at.desc())).all()
