from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user,get_project_member,record_activity
from app.models import ProjectMember,ProjectRole,Task,TaskStatus,User
from app.schemas import TaskCreate,TaskRead,TaskUpdate
from app.realtime import manager
from app.permissions import require_permission
router=APIRouter(prefix='/projects/{project_id}/tasks',tags=['tasks'])
TRANSITIONS={TaskStatus.backlog:{TaskStatus.in_progress,TaskStatus.cancelled},TaskStatus.in_progress:{TaskStatus.submitted,TaskStatus.cancelled},TaskStatus.submitted:{TaskStatus.in_review,TaskStatus.in_progress},TaskStatus.in_review:{TaskStatus.approved,TaskStatus.in_progress},TaskStatus.approved:{TaskStatus.ready_for_testing},TaskStatus.ready_for_testing:{TaskStatus.testing},TaskStatus.testing:{TaskStatus.passed,TaskStatus.failed},TaskStatus.failed:{TaskStatus.in_progress},TaskStatus.passed:{TaskStatus.ready_for_merge},TaskStatus.ready_for_merge:{TaskStatus.merged},TaskStatus.merged:set(),TaskStatus.cancelled:set()}
@router.post('',response_model=TaskRead,status_code=201)
async def create_task(project_id:str,data:TaskCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,m=get_project_member(project_id,db,user)
 require_permission(m,'edit')
 if data.assignee_id and not db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==data.assignee_id)): raise HTTPException(status_code=400,detail='Assignee must be a project member')
 t=Task(project_id=project_id,title=data.title.strip(),description=data.description,assignee_id=data.assignee_id,created_by_id=user.id);db.add(t);record_activity(db,project_id,user.id,'task.created',{'title':t.title});db.commit();db.refresh(t);await manager.broadcast(project_id,{'type':'task.created','data':{'id':t.id,'title':t.title,'status':t.status.value}});return t
@router.get('',response_model=list[TaskRead])
def list_tasks(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user);return db.scalars(select(Task).where(Task.project_id==project_id).order_by(Task.created_at.desc())).all()
@router.patch('/{task_id}',response_model=TaskRead)
async def update_task(project_id:str,task_id:str,data:TaskUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,m=get_project_member(project_id,db,user);t=db.scalar(select(Task).where(Task.id==task_id,Task.project_id==project_id))
 if not t: raise HTTPException(status_code=404,detail='Task not found')
 changes=data.model_dump(exclude_unset=True)
 if 'assignee_id' in changes:\n  require_permission(m,'manage_team')\n  if changes['assignee_id'] and not db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==changes['assignee_id'])): raise HTTPException(status_code=400,detail='Assignee must be a project member')
 new=changes.get('status')
 if new is not None and new!=t.status:
  if new not in TRANSITIONS[t.status]: raise HTTPException(status_code=409,detail=f'Invalid task transition: {t.status.value} -> {new.value}')
  if new==TaskStatus.in_review: require_permission(m,'review')
  if new==TaskStatus.approved: require_permission(m,'approve')
  if new in {TaskStatus.testing,TaskStatus.passed,TaskStatus.failed}: require_permission(m,'edit')
  if new==TaskStatus.merged: require_permission(m,'merge')
  record_activity(db,project_id,user.id,'task.status_changed',{'task_id':t.id,'from':t.status.value,'to':new.value})
 for key,value in changes.items():
  if value is not None: setattr(t,key,value)
 db.commit();db.refresh(t);await manager.broadcast(project_id,{'type':'task.updated','data':{'id':t.id,'title':t.title,'status':t.status.value}});return t
