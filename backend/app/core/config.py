from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
 app_name:str='DevSync AI API'
 environment:str='development'
 api_v1_prefix:str='/api/v1'
 secret_key:str='development-only-change-me'
 access_token_expire_minutes:int=60
 database_url:str='sqlite:///./devsync.db'
 cors_origins:str='http://localhost:5173,http://127.0.0.1:5173'
 model_config=SettingsConfigDict(env_file='.env',extra='ignore')
 @property
 def cors_origin_list(self): return [x.strip() for x in self.cors_origins.split(',') if x.strip()]
@lru_cache
def get_settings(): return Settings()
settings=get_settings()
