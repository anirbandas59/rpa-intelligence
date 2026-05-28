from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from api.routes import auth, projects, settings, stage1, stage2, stage3, stage4, use_cases

app = FastAPI(title="RPA Intelligence API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
# app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
# app.include_router(use_cases.router, prefix="/api/v1/use-cases", tags=["use-cases"])
# app.include_router(stage1.router, prefix="/api/v1/use-cases", tags=["stage1"])
# app.include_router(stage2.router, prefix="/api/v1/use-cases", tags=["stage2"])
# app.include_router(stage3.router, prefix="/api/v1/use-cases", tags=["stage3"])
# app.include_router(stage4.router, prefix="/api/v1/use-cases", tags=["stage4"])
# app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])


@app.get("/health")
def health():
    return {"status": "ok"}
