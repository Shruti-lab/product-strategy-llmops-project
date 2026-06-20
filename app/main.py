"""This file contains the main application entry point."""

from contextlib import asynccontextmanager
# Used to create startup/shutdown lifecycle hooks.
from datetime import datetime

from dotenv import load_dotenv
from fastapi import (FastAPI, Request, status)

# Raised when request data fails validation.
from fastapi.exceptions import RequestValidationError

# Allows frontend apps to call your API.
from fastapi.middleware.cors import CORSMiddleware

"""
Lets you manually return JSON.

Example:

return JSONResponse(
    status_code=404,
    content={"error": "Not found"}
)
"""
from fastapi.responses import JSONResponse

# Built-in handler when users exceed limits.
from slowapi import Limiter, _rate_limit_exceeded_handler
# Exception raised when rate limit is hit.
from slowapi.errors import RateLimitExceeded

"""
Adds a request id.

Example:

request_id=abc123

Every log for that request can be traced.
"""
from asgi_correlation_id import CorrelationIdMiddleware

from app.core.logging import logger
from app.core.config import settings
from app.api.v1.api import api_router
from app.api.v1.llm import agent
from app.core.metrics import setup_metrics
from app.core.middleware import (
    LoggingContextMiddleware,
    MetricsMiddleware,
    ProfilingMiddleware,
)
from app.core.observability import langfuse_init
from app.services.database import database_service
from app.services.memory import memory_service


load_dotenv()
langfuse_init()


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
        # await agent.create_graph()
        logger.info("graph_pre_warmed")
    except Exception as e:
        logger.exception("graph_pre_warm_failed", error=str(e))

    try:
        await memory_service.initialize()
    except Exception as e:
        logger.exception("memory_service_pre_warm_failed", error=str(e))

    yield

    await cache_service.close()
    if agent._connection_pool:
        await agent._connection_pool.close()
        logger.info("connection_pool_closed")
    logger.info("application_shutdown")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

