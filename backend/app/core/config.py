from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
 app_name:str='DevSync AI API'
 environment:str='development'
 api_v1_prefix:str='/api/v1'
 secret_key:str='development-only-change-me'
 access_token_expire_minutes:int=60
 database_url:str='sqlite:///./devsync.db'
 cors_origins:str='http://localhost:5173,http://127.0.0.1:5173'
 workspace_root:str='..'
 gemini_api_key:str=''
 gemini_model:str='gemini-2.5-flash'
 github_client_id:str=''
 github_client_secret:str=''
 github_callback_url:str='http://127.0.0.1:8000/api/v1/github/callback'
 github_token_encryption_key:str=''
 github_webhook_secret:str=''
 frontend_url:str='http://localhost:5173'
 model_config=SettingsConfigDict(env_file='.env',extra='ignore')
 @property
 def cors_origin_list(self): return [x.strip() for x in self.cors_origins.split(',') if x.strip()]
 @property
 def resolved_workspace_root(self): return Path(self.workspace_root).resolve()
@lru_cache
def get_settings(): return Settings()
settings=get_settings()
