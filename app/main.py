from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import (FastAPI, Request, status)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from asgi_correlation_id import CorrelationIdMiddleware

from app.core.logging import logger
from app.core.config import settings
from app.api.v1.api import router
from app.api.v1.llm import agent

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info(
        "application_startup",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        api_prefix=settings.API_V1_STR,
    )

    try:
        await agent.create_graph()
        logger.info("graph_pre_warmed")
    except Exception as e:
        logger.exception("graph_pre_warm_failed", error=str(e))

    yield
app = FastAPI(lifespan=lifespan