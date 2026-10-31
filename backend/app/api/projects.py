from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies import get_current_user,get_project_member,record_activity
from app.models import Project,ProjectMember,ProjectRole,User
from app.schemas import MemberCreate,MemberRead,ProjectCreate,ProjectRead
router=APIRouter(prefix='/projects',tags=['projects'])
@router.post('',response_model=ProjectRead,status_code=status.HTTP_201_CREATED)
def create_project(data:ProjectCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 p=Project(name=data.name.strip(),description=data.description,owner_id=user.id);db.add(p);db.flush();db.add(ProjectMember(project_id=p.id,user_id=user.id,role=ProjectRole.administrator));record_activity(db,p.id,user.id,'project.created',{'name':p.name});db.commit();db.refresh(p);return p
@router.get('',response_model=list[ProjectRead])
def list_projects(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 return db.scalars(select(Project).join(ProjectMember).where(ProjectMember.user_id==user.id).order_by(Project.created_at.desc())).all()
@router.get('/{project_id}',response_model=ProjectRead)
def get_project(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 p,_=get_project_member(project_id,db,user);return p
@router.get('/{project_id}/members',response_model=list[MemberRead])
def list_members(project_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 get_project_member(project_id,db,user);rows=db.execute(select(ProjectMember,User).join(User).where(ProjectMember.project_id==project_id)).all()
 return [MemberRead(id=m.id,user_id=u.id,email=u.email,display_name=u.display_name,role=m.role) for m,u in rows]
@router.post('/{project_id}/members',response_model=MemberRead,status_code=201)
def add_member(project_id:str,data:MemberCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 p,m=get_project_member(project_id,db,user)
 if m.role!=ProjectRole.administrator: raise HTTPException(status_code=403,detail='Administrator role required')
 target=db.scalar(select(User).where(User.email==str(data.email).lower()))
 if not target: raise HTTPException(status_code=404,detail='User must register before being added')
 if db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==target.id)): raise HTTPException(status_code=409,detail='User is already a project member')
 member=ProjectMember(project_id=p.id,user_id=target.id,role=data.role);db.add(member);record_activity(db,p.id,user.id,'member.added',{'member_id':target.id,'role':data.role.value});db.commit();db.refresh(member)
 return MemberRead(id=member.id,user_id=target.id,email=target.email,display_name=target.display_name,role=member.role)
