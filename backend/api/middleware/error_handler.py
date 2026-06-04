"""
Global exception handlers for FastAPI application.

Handles all exceptions from agents, tools, and validation with proper
HTTP status codes and JSON response formatting.
"""

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import get_logger
from core.exceptions import AgentExecutionError, RPABaseError

logger = get_logger("rpa_agent.api.error_handler")


async def agent_execution_error_handler(request: Request, exc: AgentExecutionError) -> JSONResponse:
    """
    Handle AgentExecutionError (422 Unprocessable Entity)

    These are expected errors from assessment pipeline - file not found,
    unsupported format, or node failures.
    """
    return JSONResponse(
        status_code=422,
        content={
            "error": "assessment_failed",
            "message": str(exc.message),
            "context": exc.context,
            "session_id": exc.context.get("session_id"),
        },
    )


async def rpa_agent_error_handler(request: Request, exc: RPABaseError) -> JSONResponse:
    """
    Handle RPAAgentError base class (500 Internal Server Error)

    These are unexpected errors from system
    """
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": str(exc.message),
            "context": exc.context,
        },
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    Handle ValueError (400 Bad Request)
    """
    return JSONResponse(
        status_code=400,
        content={
            "error": "validation_error",
            "message": str(exc),
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all other exceptions (500 Internal Server Error).

    Catch-all for unexpected errors.
    """
    logger.error(f"Unexpected error: {type(exc).__name__}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "unexpected_error",
            "message": "An unexpected error occurred",
            "detail": str(exc),
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Cast handlers to satisfy Starlette's ExceptionHandler type
    # Runtime behavior is unchanged - FastAPI only calls handlers for matching exception types
    app.add_exception_handler(
        AgentExecutionError,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            agent_execution_error_handler,
        ),
    )
    app.add_exception_handler(
        RPABaseError,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            rpa_agent_error_handler,
        ),
    )
    app.add_exception_handler(
        ValueError,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            value_error_handler,
        ),
    )
    app.add_exception_handler(
        Exception,
        cast(
            Callable[[Request, Exception], Awaitable[JSONResponse]],
            generic_error_handler,
        ),
    )
