import enum,uuid
from datetime import datetime,timezone
from sqlalchemy import Boolean,DateTime,Enum,ForeignKey,String,Text,Integer,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.core.database import Base
def new_id(): return str(uuid.uuid4())
class TimestampMixin:
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc),nullable=False)
class ProjectRole(str,enum.Enum): team_leader_project_manager='team_leader_project_manager';ui_ux_designer='ui_ux_designer';frontend_developer='frontend_developer';backend_developer='backend_developer';tester_qa_engineer='tester_qa_engineer';devops_engineer='devops_engineer';security_engineer='security_engineer';documentation_specialist='documentation_specialist';coder='coder';debugger='debugger';tester='tester';administrator='administrator'
class TaskStatus(str,enum.Enum): backlog='backlog';in_progress='in_progress';submitted='submitted';in_review='in_review';approved='approved';ready_for_testing='ready_for_testing';testing='testing';failed='failed';passed='passed';ready_for_merge='ready_for_merge';merged='merged';cancelled='cancelled'
class User(TimestampMixin,Base):
 __tablename__='users'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 email:Mapped[str]=mapped_column(String(320),unique=True,index=True,nullable=False)
 display_name:Mapped[str]=mapped_column(String(80),nullable=False)
 password_hash:Mapped[str]=mapped_column(String(255),nullable=False)
 is_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
 memberships:Mapped[list['ProjectMember']]=relationship(back_populates='user',cascade='all, delete-orphan')
class Project(TimestampMixin,Base):
 __tablename__='projects'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 name:Mapped[str]=mapped_column(String(120),nullable=False)
 description:Mapped[str]=mapped_column(Text,default='',nullable=False)
 owner_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
 github_repo_full_name:Mapped[str|None]=mapped_column(String(255),nullable=True)
 github_repo_url:Mapped[str|None]=mapped_column(String(500),nullable=True)
 github_default_branch:Mapped[str|None]=mapped_column(String(255),nullable=True)
 members:Mapped[list['ProjectMember']]=relationship(back_populates='project',cascade='all, delete-orphan')
 tasks:Mapped[list['Task']]=relationship(back_populates='project',cascade='all, delete-orphan')
class ProjectMember(TimestampMixin,Base):
 __tablename__='project_members'
 __table_args__=(UniqueConstraint('project_id','user_id',name='uq_project_member'),)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 user_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
 role:Mapped[ProjectRole]=mapped_column(Enum(ProjectRole),default=ProjectRole.frontend_developer,nullable=False)
 permissions:Mapped[str]=mapped_column(Text,default='{}',nullable=False)
 project:Mapped[Project]=relationship(back_populates='members')
 user:Mapped[User]=relationship(back_populates='memberships')
class Task(TimestampMixin,Base):
 __tablename__='tasks'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 title:Mapped[str]=mapped_column(String(180),nullable=False)
 description:Mapped[str]=mapped_column(Text,default='',nullable=False)
 status:Mapped[TaskStatus]=mapped_column(Enum(TaskStatus),default=TaskStatus.backlog,nullable=False)
 assignee_id:Mapped[str|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
 created_by_id:Mapped[str]=mapped_column(ForeignKey('users.id'),nullable=False)
 project:Mapped[Project]=relationship(back_populates='tasks')
class ActivityEvent(Base):
 __tablename__='activity_events'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 actor_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
 event_type:Mapped[str]=mapped_column(String(80),index=True,nullable=False)
 payload:Mapped[str]=mapped_column(Text,default='{}',nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),index=True,nullable=False)
class GitEvent(Base):
 __tablename__='git_events'
 __table_args__=(UniqueConstraint('project_id','commit_hash',name='uq_project_commit'),)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 actor_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
 repository_path:Mapped[str]=mapped_column(String(500),nullable=False)
 branch:Mapped[str]=mapped_column(String(255),nullable=False)
 commit_hash:Mapped[str]=mapped_column(String(40),nullable=False)
 author:Mapped[str]=mapped_column(String(255),nullable=False)
 author_email:Mapped[str]=mapped_column(String(320),nullable=False)
 committed_at:Mapped[str]=mapped_column(String(40),nullable=False)
 message:Mapped[str]=mapped_column(Text,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
class CodeReview(Base):
 __tablename__='code_reviews'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 task_id:Mapped[str]=mapped_column(ForeignKey('tasks.id',ondelete='CASCADE'),index=True,nullable=False)
 reviewer_id:Mapped[str]=mapped_column(ForeignKey('users.id'),nullable=False)
 decision:Mapped[str]=mapped_column(String(20),nullable=False)
 summary:Mapped[str]=mapped_column(Text,default='',nullable=False)
 findings:Mapped[str]=mapped_column(Text,default='',nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
class TestRun(Base):
 __tablename__='test_runs'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 task_id:Mapped[str]=mapped_column(ForeignKey('tasks.id',ondelete='CASCADE'),index=True,nullable=False)
 tester_id:Mapped[str]=mapped_column(ForeignKey('users.id'),nullable=False)
 result:Mapped[str]=mapped_column(String(20),nullable=False)
 summary:Mapped[str]=mapped_column(Text,default='',nullable=False)
 total:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 passed:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 failed:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)

class GitHubAccount(TimestampMixin,Base):
 __tablename__='github_accounts'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 user_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),unique=True,index=True,nullable=False)
 github_user_id:Mapped[str]=mapped_column(String(40),nullable=False)
 login:Mapped[str]=mapped_column(String(100),nullable=False)
 avatar_url:Mapped[str]=mapped_column(String(500),default='',nullable=False)
 access_token_encrypted:Mapped[str]=mapped_column(Text,nullable=False)
 scopes:Mapped[str]=mapped_column(Text,default='',nullable=False)

class BugReport(Base):
 __tablename__='bug_reports'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 task_id:Mapped[str]=mapped_column(ForeignKey('tasks.id',ondelete='CASCADE'),index=True,nullable=False)
 reporter_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
 title:Mapped[str]=mapped_column(String(180),nullable=False)
 description:Mapped[str]=mapped_column(Text,default='',nullable=False)
 severity:Mapped[str]=mapped_column(String(20),default='medium',nullable=False)
 status:Mapped[str]=mapped_column(String(20),default='open',nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False,index=True)
