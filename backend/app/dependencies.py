import json
from fastapi import Depends,HTTPException,status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Project,ProjectMember,User
oauth2_scheme=OAuth2PasswordBearer(tokenUrl=f'{settings.api_v1_prefix}/auth/login')
def get_current_user(token:str=Depends(oauth2_scheme),db:Session=Depends(get_db))->User:
 uid=decode_access_token(token)
 if not uid: raise HTTPException(status_code=401,detail='Invalid or expired access token',headers={'WWW-Authenticate':'Bearer'})
 user=db.get(User,uid)
 if not user or not user.is_active: raise HTTPException(status_code=401,detail='User is inactive or no longer exists')
 return user
def get_project_member(project_id:str,db:Session,user:User):
 project=db.get(Project,project_id);member=db.query(ProjectMember).filter_by(project_id=project_id,user_id=user.id).first()
 if not project or not member: raise HTTPException(status_code=404,detail='Project not found')
 return project,member
def record_activity(db,project_id,actor_id,event_type,payload):
 from app.models import ActivityEvent
 db.add(ActivityEvent(project_id=project_id,actor_id=actor_id,event_type=event_type,payload=json.dumps(payload)))
