from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user,get_project_member,record_activity
from app.models import Cycle,Milestone,User
from app.permissions import require_permission
from app.realtime import manager
from app.schemas import CycleCreate,CycleRead,CycleUpdate,MilestoneCreate,MilestoneRead,MilestoneUpdate

router=APIRouter(prefix='/projects/{project_id}',tags=['planning'])

@router.get('/cycles',response_model=list[CycleRead])
def list_cycles(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user)
 return db.scalars(select(Cycle).where(Cycle.project_id==project_id).order_by(Cycle.start_date.desc(),Cycle.created_at.desc())).all()

@router.post('/cycles',response_model=CycleRead,status_code=status.HTTP_201_CREATED)
async def create_cycle(project_id:str,data:CycleCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,member=get_project_member(project_id,db,user);require_permission(member,'edit')
 cycle=Cycle(project_id=project_id,name=data.name.strip(),goal=data.goal.strip(),start_date=data.start_date,end_date=data.end_date)
 db.add(cycle);db.flush()
 record_activity(db,project_id,user.id,'cycle.created',{'cycle_id':cycle.id,'name':cycle.name})
 db.commit();db.refresh(cycle)
 await manager.broadcast(project_id,{'type':'cycle.created','data':{'id':cycle.id,'name':cycle.name}})
 return cycle

@router.patch('/cycles/{cycle_id}',response_model=CycleRead)
async def update_cycle(project_id:str,cycle_id:str,data:CycleUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,member=get_project_member(project_id,db,user);require_permission(member,'edit')
 cycle=db.scalar(select(Cycle).where(Cycle.id==cycle_id,Cycle.project_id==project_id))
 if not cycle: raise HTTPException(status_code=404,detail='Cycle not found')
 changes=data.model_dump(exclude_unset=True)
 start=changes.get('start_date',cycle.start_date);end=changes.get('end_date',cycle.end_date)
 if start is None or end is None: raise HTTPException(status_code=422,detail='Cycle start and end dates are required')
 if end<start: raise HTTPException(status_code=422,detail='Cycle end date must be on or after start date')
 for key,value in changes.items():
  if value is not None: setattr(cycle,key,value)
 record_activity(db,project_id,user.id,'cycle.updated',{'cycle_id':cycle.id,'changes':list(changes)})
 db.commit();db.refresh(cycle)
 await manager.broadcast(project_id,{'type':'cycle.updated','data':{'id':cycle.id,'status':cycle.status}})
 return cycle

@router.get('/milestones',response_model=list[MilestoneRead])
def list_milestones(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user)
 return db.scalars(select(Milestone).where(Milestone.project_id==project_id).order_by(Milestone.due_date.asc(),Milestone.created_at.desc())).all()

@router.post('/milestones',response_model=MilestoneRead,status_code=status.HTTP_201_CREATED)
async def create_milestone(project_id:str,data:MilestoneCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,member=get_project_member(project_id,db,user);require_permission(member,'edit')
 milestone=Milestone(project_id=project_id,name=data.name.strip(),description=data.description.strip(),due_date=data.due_date)
 db.add(milestone);db.flush()
 record_activity(db,project_id,user.id,'milestone.created',{'milestone_id':milestone.id,'name':milestone.name})
 db.commit();db.refresh(milestone)
 await manager.broadcast(project_id,{'type':'milestone.created','data':{'id':milestone.id,'name':milestone.name}})
 return milestone

@router.patch('/milestones/{milestone_id}',response_model=MilestoneRead)
async def update_milestone(project_id:str,milestone_id:str,data:MilestoneUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,member=get_project_member(project_id,db,user);require_permission(member,'edit')
 milestone=db.scalar(select(Milestone).where(Milestone.id==milestone_id,Milestone.project_id==project_id))
 if not milestone: raise HTTPException(status_code=404,detail='Milestone not found')
 changes=data.model_dump(exclude_unset=True)
 for key,value in changes.items():
  if value is not None or key=='due_date': setattr(milestone,key,value)
 record_activity(db,project_id,user.id,'milestone.updated',{'milestone_id':milestone.id,'changes':list(changes)})
 db.commit();db.refresh(milestone)
 await manager.broadcast(project_id,{'type':'milestone.updated','data':{'id':milestone.id,'status':milestone.status}})
 return milestone
