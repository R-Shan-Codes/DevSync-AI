from fastapi import APIRouter,Depends,HTTPException,status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token,hash_password,verify_password
from app.dependencies import get_current_user
from app.models import User
from app.schemas import Token,UserCreate,UserRead
router=APIRouter(prefix='/auth',tags=['authentication'])
@router.post('/register',response_model=UserRead,status_code=status.HTTP_201_CREATED)
def register(data:UserCreate,db:Session=Depends(get_db)):
 email=str(data.email).lower()
 if db.scalar(select(User).where(User.email==email)): raise HTTPException(status_code=409,detail='An account with this email already exists')
 user=User(email=email,display_name=data.display_name.strip(),password_hash=hash_password(data.password));db.add(user);db.commit();db.refresh(user);return user
@router.post('/login',response_model=Token)
def login(form:OAuth2PasswordRequestForm=Depends(),db:Session=Depends(get_db)):
 user=db.scalar(select(User).where(User.email==form.username.lower()))
 if not user or not verify_password(form.password,user.password_hash) or not user.is_active: raise HTTPException(status_code=401,detail='Incorrect email or password',headers={'WWW-Authenticate':'Bearer'})
 return Token(access_token=create_access_token(user.id))
@router.get('/me',response_model=UserRead)
def me(user:User=Depends(get_current_user)): return user
