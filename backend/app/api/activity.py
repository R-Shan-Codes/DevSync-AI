import json
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user,get_project_member
from app.models import ActivityEvent,User
from app.schemas import ActivityRead
router=APIRouter(prefix='/projects/{project_id}/activity',tags=['activity'])
@router.get('',response_model=list[ActivityRead])
def list_activity(project_id:str,limit:int=Query(50,ge=1,le=200),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user);events=db.scalars(select(ActivityEvent).where(ActivityEvent.project_id==project_id).order_by(ActivityEvent.created_at.desc()).limit(limit)).all()
 return [ActivityRead(id=e.id,project_id=e.project_id,actor_id=e.actor_id,event_type=e.event_type,payload=json.loads(e.payload),created_at=e.created_at) for e in events]
