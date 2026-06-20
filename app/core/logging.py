"""Logging configuration and setup for the application.

This module provides structured logging configuration using structlog,
with environment-specific formatters and handlers. It supports both
console-friendly development logging and JSON-formatted production logging.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    override,
)

import structlog
from asgi_correlation_id import correlation_id

from app.core.config import (
    Environment,
    settings,
)

# Ensure log directory exists
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

# Context variables for storing request-specific data
_request_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar("request_context", default=None)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to the current request.

    Args:
        **kwargs: Key-value pairs to bind to the logging context
    """
    current = _request_context.get() or {}
    _request_context.set({**current, **kwargs})


def clear_context() -> None:
    """Clear all context variables for the current request."""
    _request_context.set(None)


def get_context() -> Dict[str, Any]:
    """Get the current logging context.

    Returns:
        Dict[str, Any]: Current context dictionary
    """
    return _request_context.get() or {}


def add_context_to_event_dict(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add context variables to the event dictionary.

    This processor adds any bound context variables to each log event.

    Args:
        logger: The logger instance
        method_name: The name of the logging method
        event_dict: The event dictionary to modify

    Returns:
        Dict[str, Any]: Modified event dictionary with context variables
    """
    context = get_context()
    if context:
        event_dict.update(context)
    return event_dict


def add_request_id_to_event_dict(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add the current request_id (from asgi-correlation-id) to every log event.

    Args:
        logger: The logger instance
        method_name: The name of the logging method
        event_dict: The event dictionary to modify

    Returns:
        Dict[str, Any]: Modified event dictionary with request_id
    """
    request_id = correlation_id.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def get_log_file_path() -> Path:
    """Get the current log file path based on date and environment.

    Returns:
        Path: The path to the log file
    """
    env_prefix = settings.ENVIRONMENT.value
    return settings.LOG_DIR / f"{env_prefix}-{datetime.now().strftime('%Y-%m-%d')}.jsonl"


class JsonlFileHandler(logging.Handler):
    """Custom handler for writing JSONL logs to daily files."""

    def __init__(self, file_path: Path):
        """Initialize the JSONL file handler.

        Args:
            file_path: Path to the log file where entries will be written.
        """
        super().__init__()
        self.file_path = file_path

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record to the JSONL file."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "filename": record.pathname,
                "line": record.lineno,
                "environment": settings.ENVIRONMENT.value,
            }
            extra = getattr(record, "extra", None)
            if isinstance(extra, dict):
                log_entry.update(extra)

            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            self.handleError(record)

    @override
    def close(self) -> None:
        """Close the handler."""
        super().close()


def get_structlog_processors(include_file_info: bool = True) -> List[Any]:
    """Get the structlog processors based on configuration.

    Args:
        include_file_info: Whether to include file information in the logs

    Returns:
        List[Any]: List of structlog processors
    """
    # Set up processors that are common to both outputs
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # Add context variables (user_id, session_id, etc.) to all log events
        add_context_to_event_dict,
        # Add request_id from asgi-correlation-id to all log events
        add_request_id_to_event_dict,
    ]

    # Add callsite parameters if file info is requested
    if include_file_info:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.PATHNAME,
                }
            )
        )

    # Add environment info
    processors.append(lambda _, __, event_dict: {**event_dict, "environment": settings.ENVIRONMENT.value})

    return processors


def setup_logging() -> None:
    """Configure structlog with different formatters based on environment.

    In development: pretty console output
    In staging/production: structured JSON logs
    """
    # Determine log level based on DEBUG setting
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Create file handler for JSON logs
    file_handler = JsonlFileHandler(get_log_file_path())
    file_handler.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Get shared processors
    shared_processors = get_structlog_processors(
        # Include detailed file info only in development and test
        include_file_info=settings.ENVIRONMENT in [Environment.DEVELOPMENT, Environment.TEST]
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[file_handler, console_handler],
    )

    # Configure structlog based on environment
    if settings.LOG_FORMAT == "console":
        # Development-friendly console logging
        structlog.configure(
            processors=[
                *shared_processors,
                # Use ConsoleRenderer for pretty output to the console
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Production JSON logging
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


# Initialize logging
setup_logging()

# Create logger instance
logger = structlog.get_logger()
log_level_name = "DEBUG" if settings.DEBUG else "INFO"
logger.info(
    "logging_initialized",
    environment=settings.ENVIRONMENT.value,
    log_level=log_level_name,
    log_format=settings.LOG_FORMAT,
    debug=settings.DEBUG,
)



"""
Think of this file as a **pipeline** that takes a log statement and enriches it before writing it somewhere.

## Example Request Flow

A request comes in:

```http
GET /users/123
```

Inside your route:

```python
logger.info("user_fetched", user_id=123)
```

Now let's see what happens.

---

# Step 1: Request arrives

Middleware runs first.

Some middleware may call:

```python
bind_context(
    user_id=123,
    endpoint="/users/123"
)
```

This stores request-specific information in:

```python
_request_context
```

Current context becomes:

```python
{
    "user_id": 123,
    "endpoint": "/users/123"
}
```

---

# Step 2: Correlation ID Middleware

This middleware:

```python
CorrelationIdMiddleware
```

creates a unique request id:

```python
3b9f6d20-4c55-4f3f-a0fa-4c5d5f51fabc
```

and stores it.

Every log in that request can now be traced using the same id.

---

# Step 3: Route logs something

You call:

```python
logger.info(
    "user_fetched",
    user_id=123
)
```

At this point Structlog creates an event dictionary:

```python
{
    "event": "user_fetched",
    "user_id": 123
}
```

---

# Step 4: Processors start modifying the event

This list runs:

```python
processors = [
    ...
]
```

Each processor adds information.

---

### Processor 1

```python
structlog.stdlib.add_log_level
```

Adds:

```python
{
    "level": "info"
}
```

Now:

```python
{
    "event": "user_fetched",
    "user_id": 123,
    "level": "info"
}
```

---

### Processor 2

```python
TimeStamper()
```

Adds:

```python
{
    "timestamp": "2026-06-20T10:45:22"
}
```

---

### Processor 3

```python
add_context_to_event_dict
```

This executes:

```python
context = get_context()
```

which returns:

```python
{
    "user_id": 123,
    "endpoint": "/users/123"
}
```

Then:

```python
event_dict.update(context)
```

Result:

```python
{
    "event": "user_fetched",
    "user_id": 123,
    "endpoint": "/users/123",
    "level": "info"
}
```

---

### Processor 4

```python
add_request_id_to_event_dict
```

Gets:

```python
request_id = correlation_id.get()
```

Returns:

```python
"3b9f6d20-4c55-4f3f-a0fa-4c5d5f51fabc"
```

Adds:

```python
{
    "request_id":
        "3b9f6d20-4c55-4f3f-a0fa-4c5d5f51fabc"
}
```

---

### Processor 5

In development:

```python
CallsiteParameterAdder
```

adds:

```python
{
    "filename": "user.py",
    "lineno": 45,
    "func_name": "get_user"
}
```

Very useful during debugging.

---

### Processor 6

Adds environment:

```python
{
    "environment": "development"
}
```

---

# Final Event Dict

Now Structlog has:

```python
{
    "event": "user_fetched",
    "user_id": 123,
    "endpoint": "/users/123",
    "request_id": "3b9f6d20-4c55-4f3f-a0fa-4c5d5f51fabc",
    "filename": "user.py",
    "lineno": 45,
    "environment": "development",
    "level": "info",
    "timestamp": "2026-06-20T10:45:22"
}
```

---

# Step 5: Rendering

Two possible outputs.

## Development

```python
structlog.dev.ConsoleRenderer()
```

Pretty console output:

```text
2026-06-20T10:45:22 [info] user_fetched
user_id=123
endpoint=/users/123
request_id=3b9f...
```

Easy for humans.

---

## Production

```python
JSONRenderer()
```

Produces:

```json
{
  "event":"user_fetched",
  "user_id":123,
  "request_id":"3b9f...",
  "environment":"production",
  "level":"info"
}
```

Easy for systems like:

* Elasticsearch
* Kibana
* Datadog
* Grafana

---

# Step 6: Handlers write the log

There are two handlers.

### Console Handler

```python
console_handler
```

Writes to:

```python
sys.stdout
```

Meaning:

```bash
uvicorn main:app
```

shows logs in terminal.

---

### File Handler

```python
JsonlFileHandler
```

Writes to:

```python
logs/development-2026-06-20.jsonl
```

Example file:

```json
{"event":"user_fetched","user_id":123}
{"event":"user_created","user_id":456}
{"event":"login_success","user_id":123}
```

One JSON object per line.

---

# Is all this complexity necessary?

For a small FastAPI project:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

is usually enough.

For a production system with:

* many APIs
* multiple services
* distributed tracing
* observability dashboards
* debugging production issues

the extra pieces become valuable:

1. Correlation IDs
2. Structured JSON logs
3. Request context
4. Log files
5. Centralized log search
6. Environment-aware formatting

So this logger setup is closer to what you'd see in a production SaaS platform than in a typical tutorial FastAPI project.

"""