import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.routes import auth, memory, orchestrator, projects, settings
from api.routes import stage1, stage2, stage3, stage4, use_cases
from core.scoring.effort_table import load_effort_table
from core.scoring.weight_matrix import load_weight_matrix
from db.session import get_engine
from tools.registrations import register_all_tools

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    get_engine()           # initialize connection pool
    load_weight_matrix()   # warm cache
    load_effort_table()    # warm cache
    register_all_tools()   # register agentic tools
    yield
    # Shutdown
    await get_engine().dispose()

app = FastAPI(title="RPA Intelligence API", version="0.1.0", lifespan=lifespan)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = str(uuid.uuid4())
    request_id_var.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(use_cases.router, prefix="/api/v1/use-cases", tags=["use-cases"])
app.include_router(stage1.router, prefix="/api/v1/use-cases", tags=["stage1"])
app.include_router(stage2.router, prefix="/api/v1/use-cases", tags=["stage2"])
app.include_router(stage3.router, prefix="/api/v1/use-cases", tags=["stage3"])
app.include_router(stage4.router, prefix="/api/v1/use-cases", tags=["stage4"])
app.include_router(memory.router, prefix="/api/v1/use-cases", tags=["memory"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(orchestrator.router, prefix="/api/v1", tags=["orchestrator"])


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
