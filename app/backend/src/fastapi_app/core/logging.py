"""
Centralized configuration for the application's structured logging.

This module provides the setup_logging function and request ID middleware 
for consistent, structured logging across the application using structlog.

The setup_logging function defined here will be imported and called in main.py during app startup.
This approach keeps the main application entry point clean and separates logging concerns.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings

# Context variable for storing request ID across async contexts
request_id_contextvar: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates a unique request_id for each incoming request
    and binds it to the structlog context using contextvars.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Set the request ID in the context variable
        request_id_contextvar.set(request_id)
        
        # Bind the request ID to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # Process the request
        response = await call_next(request)
        
        return response


def setup_logging(settings: Settings) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        settings: Application settings containing LOG_LEVEL configuration
    """
    # Configure structlog
    structlog.configure(
        processors=[
            # Add contextvars (like request_id) to log records
            structlog.contextvars.merge_contextvars,
            # Add log level to each log record
            structlog.stdlib.add_log_level,
            # Add logger name to each log record
            structlog.stdlib.add_logger_name,
            # Add ISO timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            # Add stack info for exceptions
            structlog.processors.StackInfoRenderer(),
            # Format exception info
            structlog.processors.format_exc_info,
            # Render as JSON
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure root logger to use structlog
    root_logger = logging.getLogger()
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Add new handler
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set log level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Prevent duplicate log messages
    root_logger.propagate = False


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Name of the logger (typically __name__)
        
    Returns:
        Configured structlog logger instance
    """
    return structlog.get_logger(name)


def log_key_event(
    logger: structlog.stdlib.BoundLogger,
    event: str,
    success: bool,
    duration_ms: float,
    error_message: str = None,
    **kwargs: Any
) -> None:
    """
    Log a key business event with standardized schema.
    
    Args:
        logger: The structlog logger instance
        event: Short, descriptive name for the event
        success: Whether the operation succeeded
        duration_ms: Time taken for the operation in milliseconds
        error_message: Error message if success is False
        **kwargs: Additional context-specific fields
    """
    log_data: Dict[str, Any] = {
        "event": event,
        "success": success,
        "duration_ms": duration_ms,
        **kwargs
    }
    
    if error_message:
        log_data["error_message"] = error_message
    
    if success:
        logger.info("Key event completed", **log_data)
    else:
        logger.error("Key event failed", **log_data)
