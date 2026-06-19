"""This file contains the user model for the application."""

from typing import (TYPE_CHECKING, List, Optional)

import bcrypt
from sqlalchemy import Column, Integer, String
from app.services.database import Base


class User(Base):
    __tablename__ = "Users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    hashed_password = Column(String)
