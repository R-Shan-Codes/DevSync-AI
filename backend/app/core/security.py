from datetime import datetime,timedelta,timezone
import jwt
from pwdlib import PasswordHash
from app.core.config import settings
password_hash=PasswordHash.recommended()
def hash_password(password:str)->str: return password_hash.hash(password)
def verify_password(password:str,hashed_password:str)->bool: return password_hash.verify(password,hashed_password)
def create_access_token(subject:str)->str:
 exp=datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_expire_minutes)
 return jwt.encode({'sub':subject,'exp':exp},settings.secret_key,algorithm='HS256')
def decode_access_token(token:str)->str|None:
 try:
  sub=jwt.decode(token,settings.secret_key,algorithms=['HS256']).get('sub')
  return sub if isinstance(sub,str) else None
 except jwt.PyJWTError: return None
