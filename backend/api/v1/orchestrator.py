"""Orchestrator API routes — start and monitor autonomous agent sessions."""
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.sse_utils import event_stream, publish_event
from db.models import AgentSession, UseCase, User, new_uuid

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OrchestrateRequest(BaseModel):
    goal: str = "full_assessment"   # full_assessment | run_stage:s1 | etc.
    mode: str = "autonomous"        # autonomous | supervised


class OrchestrateResponse(BaseModel):
    session_id: str
    status: str
    goal: str
    plan_step_count: int = 0


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    current_step: int
    goal: str
    plan: dict
    completed_stages: dict
    pending_clarification: str | None


class RespondRequest(BaseModel):
    response: str  # user's answer to the clarification question


# ---------------------------------------------------------------------------
# Background orchestration task
# ---------------------------------------------------------------------------


async def _run_orchestrator(
    session_id: str,
    use_case_id: str,
    goal: str,
    mode: str,
    db_factory,
) -> None:
    """Background task: runs the orchestrator LangGraph."""
    from agents.project_orchestrator import OrchestratorState, build_orchestrator_graph

    async with db_factory() as db:
        result = await db.execute(select(UseCase).where(UseCase.id == use_case_id))
        use_case = result.scalar_one_or_none()
        if not use_case:
            await publish_event(session_id, "error", f"UseCase {use_case_id} not found")
            return

        initial_state: OrchestratorState = {
            "session_id": session_id,
            "use_case_id": use_case_id,
            "use_case_name": use_case.name,
            "use_case_description": use_case.description or "",
            "goal": goal,
            "mode": mode,
            "plan": [],
            "current_step_index": 0,
            "completed_steps": [],
            "stage_states": {},
            "pending_clarification": None,
            "final_status": "running",
            "retry_count": 0,
            "db": db,
            "stream_events": [],
        }

        graph = build_orchestrator_graph()
        try:
            final_state = await graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": session_id}},
            )
            final_status = final_state.get("final_status", "complete")
        except Exception as e:
            logger.error(f"[orchestrator] Session {session_id} failed: {e}")
            final_status = "failed"
            await publish_event(session_id, "error", str(e)[:200])

    # Update session status in DB (separate connection to avoid nested transactions)
    db_factory_inner = db_factory
    async with db_factory_inner() as update_db:
        sess_result = await update_db.execute(
            select(AgentSession).where(AgentSession.id == session_id)
        )
        session = sess_result.scalar_one_or_none()
        if session:
            session.status = final_status
            session.updated_at = datetime.utcnow()
            await update_db.commit()

    await publish_event(session_id, "complete", final_status)
    logger.info(f"[orchestrator] Session {session_id} finished: {final_status}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/use-cases/{id}/orchestrate",
    response_model=OrchestrateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_orchestration(
    id: str,
    request: OrchestrateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start an autonomous orchestration session for a use-case."""
    result = await db.execute(select(UseCase).where(UseCase.id == id))
    use_case = result.scalar_one_or_none()
    if not use_case:
        raise HTTPException(status_code=404, detail="UseCase not found")

    session = AgentSession(
        id=new_uuid(),
        use_case_id=id,
        goal=request.goal,
        mode=request.mode,
        plan={},
        status="running",
        current_step=0,
        completed_stages={},
        created_at=datetime.utcnow(),
    )
    db.add(session)
    await db.commit()

    from db.session import get_session_factory

    db_factory = get_session_factory()

    background_tasks.add_task(
        _run_orchestrator,
        session.id,
        id,
        request.goal,
        request.mode,
        db_factory,
    )

    return OrchestrateResponse(
        session_id=session.id,
        status="running",
        goal=request.goal,
    )


@router.get(
    "/use-cases/{id}/orchestrate/{session_id}",
    response_model=SessionStatusResponse,
)
async def get_session_status(
    id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current status of an orchestration session."""
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.use_case_id == id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStatusResponse(
        session_id=session.id,
        status=session.status,
        current_step=session.current_step,
        goal=session.goal,
        plan=session.plan,
        completed_stages=session.completed_stages,
        pending_clarification=session.pending_clarification,
    )


@router.post("/use-cases/{id}/orchestrate/{session_id}/respond")
async def respond_to_clarification(
    id: str,
    session_id: str,
    request: RespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused orchestration session with a user response."""
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.use_case_id == id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.pending_clarification = None
    session.status = "running"
    session.updated_at = datetime.utcnow()
    await db.commit()

    return {"resumed": True, "session_id": session_id}


@router.get("/use-cases/{id}/agent-stream")
async def agent_stream(
    id: str,
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """SSE endpoint — streams agent step events for a session."""
    return StreamingResponse(
        event_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
