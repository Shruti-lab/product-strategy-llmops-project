from typing import Annotated
from fastapi import Depends 
from sqlalchemy.orm import Session
from database import SessionLocal

def get_db( ):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

"""
Runtime value: db_dependency is a variable holding an Annotated type.
Usage: It acts as a type alias for dependency injection.
FastAPI interpretation: "Inject a SQLAlchemy Session using get_db()."
"""