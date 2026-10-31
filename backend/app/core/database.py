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
 if 'project_members' in inspect(engine).get_table_names():
  columns={column['name'] for column in inspect(engine).get_columns('project_members')}
  if 'permissions' not in columns:
   with engine.begin() as connection:
    connection.execute(text("ALTER TABLE project_members ADD COLUMN permissions TEXT NOT NULL DEFAULT '{}'"))
