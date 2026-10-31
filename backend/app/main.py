from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import activity,auth,projects,tasks,git,reviews,test_runs,websocket
from app.core.config import settings
from app.core.database import init_db
app=FastAPI(title=settings.app_name,description='Collaborative development workflow API for DevSync AI.',version='0.2.0')
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
def startup(): init_db()
@app.get('/health',tags=['system'])
def health(): return {'status':'ok','service':'devsync-api','version':app.version}
app.include_router(auth.router,prefix=settings.api_v1_prefix)
app.include_router(projects.router,prefix=settings.api_v1_prefix)
app.include_router(tasks.router,prefix=settings.api_v1_prefix)
app.include_router(activity.router,prefix=settings.api_v1_prefix)
app.include_router(git.router,prefix=settings.api_v1_prefix)
app.include_router(reviews.router,prefix=settings.api_v1_prefix)
app.include_router(test_runs.router,prefix=settings.api_v1_prefix)
app.include_router(websocket.router)
