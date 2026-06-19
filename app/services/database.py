from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError


from app.core.config import (
    Environment,
    settings,
)
from app.models.user import User
from app.core.logging import logger

try:
    pool_size = settings.POSTGRES_POOL_SIZE
    max_overflow = settings.POSTGRES_MAX_OVERFLOW

    # Create engine with appropriate pool configuration
    connection_url = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )

    engine = create_engine(connection_url, pool_pre_ping=True, pool_size=pool_size, max_overflow=max_overflow,
        pool_timeout=30,  # Connection timeout (seconds)
        pool_recycle=1800,  # Recycle connections after 30 minutes)
        )

    logger.info("database_initialized", environment=settings.ENVIRONMENT.value, pool_size=pool_size, max_overflow=max_overflow)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base = declarative_base()
    Base.metadata.create_all(bind=engine)
    logger.info("database_initialized", environment=settings.ENVIRONMENT.value)
        

except SQLAlchemyError as e:
    logger.error("database_initialization_error", error=str(e), environment=settings.ENVIRONMENT.value)
    # In production, don't raise - allow app to start even with DB issues
    if settings.ENVIRONMENT != Environment.PRODUCTION:
        raise
        
except Exception as e:
    logger.error("database_initialization_error", error=str(e), environment=settings.ENVIRONMENT.value)
    # In production, don't raise - allow app to start even with DB issues
    if settings.ENVIRONMENT != Environment.PRODUCTION:
        raise

