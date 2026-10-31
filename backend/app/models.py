import enum,uuid
from datetime import datetime,timezone
from sqlalchemy import Boolean,DateTime,Enum,ForeignKey,String,Text
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.core.database import Base
def new_id(): return str(uuid.uuid4())
class TimestampMixin:
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc),nullable=False)
class ProjectRole(str,enum.Enum): coder='coder';debugger='debugger';tester='tester';administrator='administrator'
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
 members:Mapped[list['ProjectMember']]=relationship(back_populates='project',cascade='all, delete-orphan')
 tasks:Mapped[list['Task']]=relationship(back_populates='project',cascade='all, delete-orphan')
class ProjectMember(TimestampMixin,Base):
 __tablename__='project_members'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 project_id:Mapped[str]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),index=True,nullable=False)
 user_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
 role:Mapped[ProjectRole]=mapped_column(Enum(ProjectRole),default=ProjectRole.coder,nullable=False)
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
