"""This file contains the main application entry point."""

from contextlib import asynccontextmanager
# Used to create startup/shutdown lifecycle hooks.
from datetime import datetime
from typing import Any

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
from app.core.limiter import limiter
from app.api.v1.llm import agent
from app.core.metrics import setup_metrics
from app.core.middleware import (
    LoggingContextMiddleware,
    MetricsMiddleware,
    ProfilingMiddleware,
)
from app.core.observability import langfuse_init
from app.services.dependencies import db_dependency

from sqlalchemy import text


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
        await agent.create_graph()
        logger.info("graph_pre_warmed")
    except Exception as e:
        logger.exception("graph_pre_warm_failed", error=str(e))

    # try:
    #     await memory_service.initialize()
    # except Exception as e:
    #     logger.exception("memory_service_pre_warm_failed", error=str(e))

    yield

    # await cache_service.close()
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


# Set up Prometheus metrics
setup_metrics(app)


# Add logging context middleware (must be added before other middleware to capture context)
app.add_middleware(LoggingContextMiddleware)


# Add custom metrics middleware
# app.add_middleware(MetricsMiddleware)


# Add profiling middleware (DEBUG only — saves HTML to /tmp on slow requests)
if settings.DEBUG:
    app.add_middleware(ProfilingMiddleware)

# Add correlation ID middleware — must be outermost so request_id is set before all others
app.add_middleware(CorrelationIdMiddleware)

# Set up rate limiter exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]


# Add validation exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors from request data.

    Args:
        request: The request that caused the validation error
        exc: The validation error

    Returns:
        JSONResponse: A formatted error response
    """
    # Log the validation error
    logger.error(
        "validation_error",
        client_host=request.client.host if request.client else "unknown",
        path=request.url.path,
        errors=str(exc.errors()),
    )

    # Format the errors to be more user-friendly
    formatted_errors = []
    for error in exc.errors():
        loc = " -> ".join([str(loc_part) for loc_part in error["loc"] if loc_part != "body"])
        formatted_errors.append({"field": loc, "message": error["msg"]})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": formatted_errors},
    )


# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["root"][0])
async def root(request: Request):
    """Root endpoint returning basic API information."""
    logger.info("root_endpoint_called")
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "environment": settings.ENVIRONMENT.value,
        "swagger_url": "/docs",
        "redoc_url": "/redoc",
    }

@app.get("/health")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["health"][0])
async def health_check(request: Request, db: db_dependency) -> JSONResponse:
    """Health check endpoint with environment-specific information.

    Returns:
        JSONResponse: Health status payload, with HTTP 503 when the
        database is unreachable so load balancers can drop the instance.
    """
    logger.info("health_check_called")

    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(
            "database_health_check_failed",
            error=str(e),
        )
        db_healthy = False

    response = {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT.value,
        "components": {"api": "healthy", "database": "healthy" if db_healthy else "unhealthy"},
        "timestamp": datetime.now().isoformat(),
    }

    # If DB is unhealthy, set the appropriate status code
    status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(content=response, status_code=status_code)