from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,Session,sessionmaker
from app.core.config import settings
connect_args={'check_same_thread':False} if settings.database_url.startswith('sqlite') else {}
engine=create_engine(settings.database_url,connect_args=connect_args,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False,expire_on_commit=False)
class Base(DeclarativeBase): pass
def get_db()->Generator[Session,None,None]:
 db=SessionLocal()
 try: yield db
 finally: db.close()
def init_db():
 from app import models  # noqa
 Base.metadata.create_all(bind=engine)
 # Safe additive migration for existing SQLite installations.
 from sqlalchemy import inspect, text
 if 'projects' in inspect(engine).get_table_names():
  columns={column['name'] for column in inspect(engine).get_columns('projects')}
  with engine.begin() as connection:
   if 'github_repo_full_name' not in columns: connection.execute(text('ALTER TABLE projects ADD COLUMN github_repo_full_name VARCHAR(255)'))
   if 'github_repo_url' not in columns: connection.execute(text('ALTER TABLE projects ADD COLUMN github_repo_url VARCHAR(500)'))
   if 'github_default_branch' not in columns: connection.execute(text('ALTER TABLE projects ADD COLUMN github_default_branch VARCHAR(255)'))
 if 'project_members' in inspect(engine).get_table_names():
  columns={column['name'] for column in inspect(engine).get_columns('project_members')}
  if 'permissions' not in columns:
   with engine.begin() as connection:
    connection.execute(text("ALTER TABLE project_members ADD COLUMN permissions TEXT NOT NULL DEFAULT '{}'"))
