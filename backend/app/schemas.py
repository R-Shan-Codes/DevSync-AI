from datetime import datetime
from pydantic import BaseModel,ConfigDict,EmailStr,Field,model_validator
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
class MemberCreate(BaseModel): email:EmailStr;role:ProjectRole=ProjectRole.frontend_developer
class MemberUpdate(BaseModel): role:ProjectRole|None=None;permissions:dict[str,bool]|None=None
class MemberRead(BaseModel): id:str;user_id:str;email:EmailStr;display_name:str;role:str;permissions:dict[str,bool]
class TaskCreate(BaseModel): title:str=Field(min_length=2,max_length=180);description:str=Field(default='',max_length=10000);assignee_id:str|None=None
class TaskUpdate(BaseModel): title:str|None=Field(default=None,min_length=2,max_length=180);description:str|None=Field(default=None,max_length=10000);status:TaskStatus|None=None;assignee_id:str|None=None
class TaskRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:str;project_id:str;title:str;description:str;status:TaskStatus;assignee_id:str|None;created_by_id:str;created_at:datetime;updated_at:datetime
class ActivityRead(BaseModel): id:str;project_id:str;actor_id:str;event_type:str;payload:dict;created_at:datetime
class GitSyncRequest(BaseModel): repository_path:str=Field(min_length=1,max_length=500);commit_limit:int=Field(default=30,ge=1,le=100)
class GitEventRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:str;project_id:str;repository_path:str;branch:str;commit_hash:str;author:str;author_email:str;committed_at:str;message:str;created_at:datetime
class ReviewCreate(BaseModel):
 task_id:str;decision:str=Field(pattern='^(approved|changes_requested|commented)$');summary:str=Field(default='',max_length=5000);findings:str=Field(default='',max_length=20000)
class ReviewRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:str;project_id:str;task_id:str;reviewer_id:str;decision:str;summary:str;findings:str;created_at:datetime
class TestRunCreate(BaseModel):
 task_id:str;result:str=Field(pattern='^(passed|failed|blocked)$');summary:str=Field(default='',max_length=10000);total:int=Field(default=0,ge=0);passed:int=Field(default=0,ge=0);failed:int=Field(default=0,ge=0)
 @model_validator(mode='after')
 def validate_counts(self):
  if self.passed+self.failed>self.total: raise ValueError('passed + failed cannot exceed total')
  if self.result=='passed' and self.failed: raise ValueError('A passed run cannot contain failed tests')
  if self.result=='failed' and not self.failed: raise ValueError('A failed run must contain at least one failed test')
  return self
class TestRunRead(BaseModel):
 model_config=ConfigDict(from_attributes=True)
 id:str;project_id:str;task_id:str;tester_id:str;result:str;summary:str;total:int;passed:int;failed:int;created_at:datetime

class AIAssistRequest(BaseModel):
 project_id:str
 role:str=Field(pattern='^(team_leader_project_manager|ui_ux_designer|frontend_developer|backend_developer|tester_qa_engineer|devops_engineer|security_engineer|documentation_specialist|coder|debugger|tester))
 prompt:str=Field(min_length=2,max_length=12000)
