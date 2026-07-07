"""Authentication and authorization endpoints for the API.

This module provides endpoints for user registration, login, session management,
and token verification.
"""

from sys import prefix
from typing import List, Annotated


from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from fastapi.security import  OAuth2PasswordRequestForm
from starlette import status
from app.core.limiter import limiter
from app.core.config import settings

from app.schemas.user import UserCreate, TokenData
from app.services.user_db import create_user, authenticate_user, create_access_token
from app.services.dependencies import db_dependency


router = APIRouter()


@router.post("/signup")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["signup"][0])
def signup(request: Request,user: UserCreate,db: db_dependency):
    return create_user(
        db=db,
        email=user.email,
        password=user.password,
    )



@router.post('/login',response_model=TokenData)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["login"][0])
def signin(request: Request,form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    """
    Authenticates user credentials and returns a JWT token if valid.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate User"
        )
    email = user.email
    user_id = user.id
    token = create_access_token(user_id, email)

    return {"token": token, "token_type": "bearer"}