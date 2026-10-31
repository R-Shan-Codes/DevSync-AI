from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user,get_project_member,record_activity
from app.models import Project,ProjectMember,ProjectRole,User
from app.schemas import MemberCreate,MemberRead,MemberUpdate,ProjectCreate,ProjectRead
from app.permissions import PERMISSIONS,permissions_for,require_permission,normalize_role
router=APIRouter(prefix='/projects',tags=['projects'])
def member_read(m,u): return MemberRead(id=m.id,user_id=u.id,email=u.email,display_name=u.display_name,role=normalize_role(m.role),permissions=permissions_for(m))
@router.post('',response_model=ProjectRead,status_code=status.HTTP_201_CREATED)
def create_project(data:ProjectCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 p=Project(name=data.name.strip(),description=data.description,owner_id=user.id);db.add(p);db.flush();db.add(ProjectMember(project_id=p.id,user_id=user.id,role=ProjectRole.team_leader_project_manager));record_activity(db,p.id,user.id,'project.created',{'name':p.name});db.commit();db.refresh(p);return p
@router.get('',response_model=list[ProjectRead])
def list_projects(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 return db.scalars(select(Project).join(ProjectMember).where(ProjectMember.user_id==user.id).order_by(Project.created_at.desc())).all()
@router.get('/{project_id}',response_model=ProjectRead)
def get_project(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 p,_=get_project_member(project_id,db,user);return p
@router.get('/{project_id}/members',response_model=list[MemberRead])
def list_members(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user);rows=db.execute(select(ProjectMember,User).join(User).where(ProjectMember.project_id==project_id)).all()
 return [member_read(m,u) for m,u in rows]
@router.get('/{project_id}/members/me',response_model=MemberRead)
def my_membership(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,m=get_project_member(project_id,db,user);return member_read(m,user)
@router.post('/{project_id}/members',response_model=MemberRead,status_code=201)
def add_member(project_id:str,data:MemberCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 p,m=get_project_member(project_id,db,user);require_permission(m,'manage_team')
 target=db.scalar(select(User).where(User.email==str(data.email).lower()))
 if not target: raise HTTPException(status_code=404,detail='User must register before being added')
 if db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==target.id)): raise HTTPException(status_code=409,detail='User is already a project member')
 member=ProjectMember(project_id=p.id,user_id=target.id,role=data.role);db.add(member);record_activity(db,p.id,user.id,'member.added',{'member_id':target.id,'role':data.role.value});db.commit();db.refresh(member);return member_read(member,target)
@router.patch('/{project_id}/members/{member_id}',response_model=MemberRead)
def update_member(project_id:str,member_id:str,data:MemberUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,actor=get_project_member(project_id,db,user);require_permission(actor,'manage_team')
 target=db.scalar(select(ProjectMember).where(ProjectMember.id==member_id,ProjectMember.project_id==project_id))
 if not target: raise HTTPException(status_code=404,detail='Project member not found')
 if target.user_id==user.id and data.role is not None: raise HTTPException(status_code=400,detail='You cannot change your own role')
 if data.role is not None:
  target.role=data.role
  if data.permissions is None: target.permissions='{}'
 if data.permissions is not None:
  if set(data.permissions)-set(PERMISSIONS): raise HTTPException(status_code=422,detail='Unknown permission')
  import json
  target.permissions=json.dumps(data.permissions)
 record_activity(db,project_id,user.id,'member.permissions_updated',{'member_id':target.id})
 db.commit();db.refresh(target);return member_read(target,target.user)
@router.delete('/{project_id}/members/{member_id}',status_code=204)
def remove_member(project_id:str,member_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 _,actor=get_project_member(project_id,db,user);require_permission(actor,'manage_team')
 target=db.scalar(select(ProjectMember).where(ProjectMember.id==member_id,ProjectMember.project_id==project_id))
 if not target: raise HTTPException(status_code=404,detail='Project member not found')
 if target.user_id==user.id: raise HTTPException(status_code=400,detail='You cannot remove yourself from the project')
 db.delete(target);record_activity(db,project_id,user.id,'member.removed',{'member_id':member_id});db.commit()
