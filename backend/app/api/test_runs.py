from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user, get_project_member, record_activity
from app.models import ProjectRole, Task, TestRun, User
from app.realtime import manager
from app.schemas import TestRunCreate, TestRunRead

router = APIRouter(prefix="/projects/{project_id}/test-runs", tags=["test-runs"])

@router.post("", response_model=TestRunRead, status_code=201)
async def create_test_run(project_id: str, data: TestRunCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = get_project_member(project_id, db, user)
    if member.role not in {ProjectRole.tester, ProjectRole.administrator}:
        raise HTTPException(status_code=403, detail="Tester or administrator role required")
    if not db.scalar(select(Task).where(Task.id == data.task_id, Task.project_id == project_id)):
        raise HTTPException(status_code=404, detail="Task not found in this project")
    run = TestRun(project_id=project_id, task_id=data.task_id, tester_id=user.id, result=data.result, summary=data.summary, total=data.total, passed=data.passed, failed=data.failed)
    db.add(run)
    record_activity(db, project_id, user.id, "test_run.created", {"task_id": data.task_id, "result": data.result, "failed": data.failed})
    db.commit()
    db.refresh(run)
    await manager.broadcast(project_id, {"type": "test_run.created", "data": {"id": run.id, "task_id": run.task_id, "result": run.result, "failed": run.failed}})
    return run

@router.get("", response_model=list[TestRunRead])
def list_test_runs(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_member(project_id, db, user)
    return db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())).all()
