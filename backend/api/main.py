"""
FastAPI application entry point for RPA Intelligence Platform.

Configures the main FastAPI application with lifespan events, middleware,
and API routes. Handles application startup (database pool initialization,
cache warming, tool registration) and shutdown (connection cleanup).

Key components:
- lifespan: Startup/shutdown logic for resource management
- request_id_middleware: Adds unique request ID to every request/response
- CORS middleware: Enables frontend communication
- Health endpoints: Application and database health checks

All API routes are mounted under /api/v1 prefix.
"""

import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.v1 import v1_router
from core.scoring.effort_table import load_effort_table
from core.scoring.weight_matrix import load_weight_matrix
from db.session import get_engine
from tools.registrations import register_all_tools

# Context variable for tracking request IDs across async operations
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.

    Startup: Initializes database connection pool, warms caches for scoring
    reference data, and registers all agentic tools for LangGraph workflows.

    Shutdown: Disposes database engine and closes all connections cleanly.

    Args:
        app: FastAPI application instance

    Yields:
        Control to application during runtime
    """
    # Startup: Initialize resources
    get_engine()  # Initialize async database connection pool
    load_weight_matrix()  # Warm cache with weight matrix from JSON
    load_effort_table()  # Warm cache with effort estimates from JSON
    register_all_tools()  # Register all agentic tools for LangGraph

    yield

    # Shutdown: Cleanup resources
    await get_engine().dispose()  # Close all database connections


app = FastAPI(title="RPA Intelligence API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """
    Middleware to add unique request ID to every request/response.

    Generates a UUID for each incoming request, stores it in context variable
    for access in logging/tracing, and adds it to response headers. Enables
    request tracking across async operations and distributed logging.

    Args:
        request: Incoming HTTP request
        call_next: Next middleware/handler in chain

    Returns:
        Response with X-Request-ID header added
    """
    # Generate unique request ID
    rid = str(uuid.uuid4())
    # Store in context variable for access in downstream code
    request_id_var.set(rid)
    # Process request
    response = await call_next(request)
    # Add request ID to response headers for client tracking
    response.headers["X-Request-ID"] = rid
    return response


# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,  # Enable cookies/auth headers
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Mount v1 API routes under /api/v1 prefix
app.include_router(v1_router, prefix="/api/v1")


# Health check endpoints
@app.get("/")
async def health_check():
    """
    Basic application health check.

    Returns:
        Status OK if application is running
    """
    return {"status": "ok"}


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """
    Database connection health check.

    Executes a simple query to verify database connectivity. Used by
    monitoring systems and deployment health checks.

    Args:
        db: Async database session (injected)

    Returns:
        Status OK with database connection confirmation
    """
    # Execute simple query to verify database connectivity
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
