from datetime import datetime, timedelta
from typing import Annotated, Optional


from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.util import deprecated
from starlette import status

from app.core.logging import logger
from app.services.dependencies import db_dependency
from app.schemas import Session
from app.models.user import User
from app.core.config import settings

#We use bcrypt to securely hash user passwords:
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/login")

def create_user(db: db_dependency, email: str, password):
    """Creates a new user.

        Args:
            db : database session
            email: User's email address
            password: Hashed password

        Returns:
            User: The created user
    """
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(email=email,hashed_password=bcrypt_context.hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user_created", email=email)
    return user

def authenticate_user(db: db_dependency, email: str, password: str):
    """
    Verifies the username and password against stored hashed password.
    Returns the user if authentication is successful, otherwise returns False.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user

def create_access_token(user_id: int, email: str ):
    encode = {"sub": email, "id":user_id}
    expires = datetime.now() + timedelta(days=settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS)
    encode.update({"exp": expires})
    return jwt.encode(encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_user(db: db_dependency, token: str = Depends(oauth2_bearer)) -> User:
    """
    Decodes the JWT token and retrieves user details.
    Raises an exception if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
       )
        # token_data = TokenData(email=email)
    except JWTError:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return user



def get_current_session(db: db_dependency,token: str = Depends(oauth2_bearer)) -> Session:
    """
    Returns the currently authenticated user from the JWT.
    """

    # credentials_exception = HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Could not validate credentials",
    #     headers={"WWW-Authenticate": "Bearer"},
    # )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        session_id: str | None = payload.get("sub")
        user_id: int | None = payload.get("id")
        if session_id is None:
            logger.error("session_id_not_found", token_part=token[:10] + "...")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = db.query(User).filter(User.email == session_id).first()
        if user is None:
            raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        print(f'This is user_db.py AND THIS IS SESSION ID: {session_id}')

        return {
            "session_id":session_id,
            "user_id":user_id,
            "email":session_id
        }

    except ValueError as ve:
        logger.exception("token_validation_failed", error=str(ve))
        raise HTTPException(
            status_code=422,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials. Invalid or expired or missing token.",
            headers={"WWW-Authenticate": "Bearer"},
        )