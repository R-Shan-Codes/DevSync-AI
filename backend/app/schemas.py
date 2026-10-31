from datetime import datetime
from pydantic import BaseModel,ConfigDict,EmailStr,Field
from app.models import ProjectRole,TaskStatus
class UserCreate(BaseModel): email:EmailStr;display_name:str=Field(min_length=1,max_length=80);password:str=Field(min_length=8,max_length=128)
class UserRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:str;email:EmailStr;display_name:str;is_active:bool;created_at:datetime
class Token(BaseModel): access_token:str;token_type:str='bearer'
class ProjectCreate(BaseModel): name:str=Field(min_length=2,max_length=120);description:str=Field(default='',max_length=4000)
class ProjectRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:str;name:str;description:str;owner_id:str;created_at:datetime
class MemberCreate(BaseModel): email:EmailStr;role:ProjectRole=ProjectRole.coder
class MemberRead(BaseModel): id:str;user_id:str;email:EmailStr;display_name:str;role:ProjectRole
class TaskCreate(BaseModel): title:str=Field(min_length=2,max_length=180);description:str=Field(default='',max_length=10000);assignee_id:str|None=None
class TaskUpdate(BaseModel): title:str|None=Field(default=None,min_length=2,max_length=180);description:str|None=Field(default=None,max_length=10000);status:TaskStatus|None=None;assignee_id:str|None=None
class TaskRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:str;project_id:str;title:str;description:str;status:TaskStatus;assignee_id:str|None;created_by_id:str;created_at:datetime;updated_at:datetime
class ActivityRead(BaseModel): id:str;project_id:str;actor_id:str;event_type:str;payload:dict;created_at:datetime
