from datetime import datetime, timedelta
from typing import Annotated


from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.util import deprecated
from starlette import status


from dependencies import db_dependency
from app.models.user import Users


def create_user(db: db_dependency, email: str, password):
    