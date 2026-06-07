"""
Global exception handlers for FastAPI application.

Maps Python exceptions to appropriate HTTP responses with consistent JSON
formatting. Provides tiered error handling: expected errors (AgentExecutionError)
vs unexpected errors (generic Exception). Logs unexpected errors for debugging
while returning safe error messages to clients.

Exception hierarchy:
- AgentExecutionError (422): Expected assessment failures (file issues, LLM errors)
- RPABaseError (500): Unexpected system errors
- ValueError (400): Input validation failures
- Exception (500): Catch-all for unhandled errors

All handlers return JSON: {"error": str, "message": str, "context": dict}
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
    Handle AgentExecutionError (422 Unprocessable Entity).

    Expected errors from assessment pipeline: document parsing failures, LLM
    provider issues, validation errors, or agent node failures. Returns 422
    to indicate request was understood but couldn't be processed.

    Args:
        request: HTTP request that triggered error
        exc: AgentExecutionError with message and context

    Returns:
        JSON response with error details and session_id for tracing
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
    Handle RPABaseError (500 Internal Server Error).

    Unexpected system-level errors that don't fit AgentExecutionError category.
    Returns 500 to indicate server-side failure.

    Args:
        request: HTTP request that triggered error
        exc: RPABaseError with message and context

    Returns:
        JSON response with error details
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
    Handle ValueError (400 Bad Request).

    Input validation failures from Pydantic or manual validation. Returns 400
    to indicate client should fix request data.

    Args:
        request: HTTP request that triggered error
        exc: ValueError from validation

    Returns:
        JSON response with validation error message
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

    Catch-all for unhandled exceptions. Logs full stack trace for debugging
    while returning generic error message to client (hides internal details).

    Args:
        request: HTTP request that triggered error
        exc: Any unhandled exception

    Returns:
        JSON response with generic error message and exception detail
    """
    # Log full error details with stack trace for debugging
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
    """
    Register all exception handlers on the FastAPI application.

    Attaches custom error handlers to FastAPI app in order of specificity:
    most specific (AgentExecutionError) to most generic (Exception). FastAPI
    matches exceptions top-down, so order matters.

    Args:
        app: FastAPI application instance
    """
    # Cast handlers to satisfy Starlette's ExceptionHandler type signature
    # Runtime behavior unchanged - FastAPI calls handlers only for matching exception types
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
