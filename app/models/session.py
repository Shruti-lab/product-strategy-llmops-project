"""This file contains the session model for the application."""
from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, Text, DateTime, func
from sqlalchemy.orm import relationship

from app.services.database import Base

from typing import (
    TYPE_CHECKING,
    Optional,
)


if TYPE_CHECKING:
    from app.models.user import User




class UserSession(Base):
    """Session model for storing user sessions."""

    __tablename__ = "UserSessions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("Users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # email = Column(String, nullable=False)
    user_message = Column(Text, nullable=False)
    agent_message = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="sessions")