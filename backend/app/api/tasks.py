from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user,get_project_member,record_activity
from app.models import Cycle,Milestone,ProjectMember,ProjectRole,Task,TaskComment,TaskStatus,User
from app.schemas import TaskCommentCreate,TaskCommentRead,TaskCreate,TaskRead,TaskUpdate
from app.realtime import manager
from app.permissions import require_permission
router=APIRouter(prefix='/projects/{project_id}/tasks',tags=['tasks'])
TRANSITIONS={TaskStatus.backlog:{TaskStatus.in_progress,TaskStatus.cancelled},TaskStatus.in_progress:{TaskStatus.submitted,TaskStatus.cancelled},TaskStatus.submitted:{TaskStatus.in_review,TaskStatus.in_progress},TaskStatus.in_review:{TaskStatus.approved,TaskStatus.in_progress},TaskStatus.approved:{TaskStatus.ready_for_testing},TaskStatus.ready_for_testing:{TaskStatus.testing},TaskStatus.testing:{TaskStatus.passed,TaskStatus.failed},TaskStatus.failed:{TaskStatus.in_progress},TaskStatus.passed:{TaskStatus.ready_for_merge},TaskStatus.ready_for_merge:{TaskStatus.merged},TaskStatus.merged:set(),TaskStatus.cancelled:set()}
@router.post('',response_model=TaskRead,status_code=201)
async def create_task(project_id:str,data:TaskCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,m=get_project_member(project_id,db,user)
 require_permission(m,'edit')
 if data.assignee_id and not db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==data.assignee_id)): raise HTTPException(status_code=400,detail='Assignee must be a project member')
 if data.cycle_id and not db.scalar(select(Cycle).where(Cycle.id==data.cycle_id,Cycle.project_id==project_id)): raise HTTPException(status_code=400,detail='Cycle must belong to this project')
 if data.milestone_id and not db.scalar(select(Milestone).where(Milestone.id==data.milestone_id,Milestone.project_id==project_id)): raise HTTPException(status_code=400,detail='Milestone must belong to this project')
 if data.parent_task_id and not db.scalar(select(Task).where(Task.id==data.parent_task_id,Task.project_id==project_id)): raise HTTPException(status_code=400,detail='Parent task must belong to this project')
 t=Task(project_id=project_id,title=data.title.strip(),description=data.description,assignee_id=data.assignee_id,created_by_id=user.id,priority=data.priority,due_date=data.due_date,cycle_id=data.cycle_id,milestone_id=data.milestone_id,parent_task_id=data.parent_task_id);db.add(t);record_activity(db,project_id,user.id,'task.created',{'title':t.title});db.commit();db.refresh(t);await manager.broadcast(project_id,{'type':'task.created','data':{'id':t.id,'title':t.title,'status':t.status.value}});return t
@router.get('',response_model=list[TaskRead])
def list_tasks(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user);return db.scalars(select(Task).where(Task.project_id==project_id).order_by(Task.created_at.desc())).all()
@router.patch('/{task_id}',response_model=TaskRead)
async def update_task(project_id:str,task_id:str,data:TaskUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,m=get_project_member(project_id,db,user);t=db.scalar(select(Task).where(Task.id==task_id,Task.project_id==project_id))
 if not t: raise HTTPException(status_code=404,detail='Task not found')
 changes=data.model_dump(exclude_unset=True)
 if any(key in changes for key in ('title','description','priority','due_date','cycle_id','milestone_id','parent_task_id')): require_permission(m,'edit')
 if changes.get('cycle_id') and not db.scalar(select(Cycle).where(Cycle.id==changes['cycle_id'],Cycle.project_id==project_id)): raise HTTPException(status_code=400,detail='Cycle must belong to this project')
 if changes.get('milestone_id') and not db.scalar(select(Milestone).where(Milestone.id==changes['milestone_id'],Milestone.project_id==project_id)): raise HTTPException(status_code=400,detail='Milestone must belong to this project')
 if 'parent_task_id' in changes:
  parent_id=changes['parent_task_id']
  if parent_id==task_id: raise HTTPException(status_code=400,detail='A task cannot be its own parent')
  if parent_id and not db.scalar(select(Task).where(Task.id==parent_id,Task.project_id==project_id)): raise HTTPException(status_code=400,detail='Parent task must belong to this project')
  cursor=parent_id
  visited=set()
  while cursor:
   if cursor==task_id: raise HTTPException(status_code=409,detail='Task hierarchy cannot contain cycles')
   if cursor in visited: raise HTTPException(status_code=409,detail='Existing task hierarchy contains a cycle')
   visited.add(cursor)
   ancestor=db.scalar(select(Task).where(Task.id==cursor,Task.project_id==project_id))
   cursor=ancestor.parent_task_id if ancestor else None
 if 'assignee_id' in changes:
  require_permission(m,'manage_team')
  if changes['assignee_id'] and not db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==changes['assignee_id'])):
   raise HTTPException(status_code=400,detail='Assignee must be a project member')
 new=changes.get('status')
 if new is not None and new!=t.status:
  if new not in TRANSITIONS[t.status]: raise HTTPException(status_code=409,detail=f'Invalid task transition: {t.status.value} -> {new.value}')
  if new==TaskStatus.in_review: require_permission(m,'review')
  if new==TaskStatus.approved: require_permission(m,'approve')
  if new in {TaskStatus.testing,TaskStatus.passed,TaskStatus.failed}: require_permission(m,'edit')
  if new==TaskStatus.merged: require_permission(m,'merge')
  record_activity(db,project_id,user.id,'task.status_changed',{'task_id':t.id,'from':t.status.value,'to':new.value})
 for key,value in changes.items():
  if value is not None or key=='due_date': setattr(t,key,value)
 db.commit();db.refresh(t);await manager.broadcast(project_id,{'type':'task.updated','data':{'id':t.id,'title':t.title,'status':t.status.value}});return t


@router.get('/{task_id}/comments',response_model=list[TaskCommentRead])
def list_task_comments(project_id:str,task_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user)
 task=db.scalar(select(Task).where(Task.id==task_id,Task.project_id==project_id))
 if not task: raise HTTPException(status_code=404,detail='Task not found')
 return db.scalars(select(TaskComment).where(TaskComment.project_id==project_id,TaskComment.task_id==task_id).order_by(TaskComment.created_at.asc())).all()

@router.post('/{task_id}/comments',response_model=TaskCommentRead,status_code=201)
async def create_task_comment(project_id:str,task_id:str,data:TaskCommentCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,member=get_project_member(project_id,db,user)
 require_permission(member,'edit')
 task=db.scalar(select(Task).where(Task.id==task_id,Task.project_id==project_id))
 if not task: raise HTTPException(status_code=404,detail='Task not found')
 body=data.body.strip()
 if not body: raise HTTPException(status_code=422,detail='Comment cannot be empty')
 comment=TaskComment(project_id=project_id,task_id=task_id,author_id=user.id,body=body)
 db.add(comment);db.flush()
 record_activity(db,project_id,user.id,'task.comment_created',{'task_id':task_id,'comment_id':comment.id})
 db.commit();db.refresh(comment)
 await manager.broadcast(project_id,{'type':'task.comment_created','data':{'task_id':task_id,'comment_id':comment.id}})
 return comment
