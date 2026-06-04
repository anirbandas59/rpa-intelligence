"""V1 API Router - aggregates all v1 sub-routers"""

from fastapi import APIRouter

from . import (
    auth,
    memory,
    orchestrator,
    projects,
    settings,
    stage1,
    stage2,
    stage3,
    stage4,
    use_cases,
)

v1_router = APIRouter()

v1_router.include_router(orchestrator.router, prefix="/orchestrator", tags=["orchestrator"])
v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
v1_router.include_router(projects.router, prefix="/projects", tags=["projects"])
v1_router.include_router(use_cases.router, prefix="/use-cases", tags=["use-cases"])
v1_router.include_router(stage1.router, prefix="/stage1", tags=["stage1"])
v1_router.include_router(stage2.router, prefix="/stage2", tags=["stage2"])
v1_router.include_router(stage3.router, prefix="/stage3", tags=["stage3"])
v1_router.include_router(stage4.router, prefix="/stage4", tags=["stage4"])
v1_router.include_router(memory.router, prefix="/memory", tags=["memory"])
v1_router.include_router(settings.router, prefix="/settings", tags=["settings"])
