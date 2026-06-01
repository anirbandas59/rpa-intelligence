"""Unit tests for the project orchestrator agent nodes and routing."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from agents.project_orchestrator import (
    OrchestratorState,
    evaluate_node,
    plan_node,
    route_after_evaluate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides) -> OrchestratorState:
    state: OrchestratorState = {
        "session_id": "test-session-001",
        "use_case_id": "uc-001",
        "use_case_name": "Invoice Processing",
        "use_case_description": "Automate invoice data extraction from PDFs",
        "goal": "full_assessment",
        "mode": "autonomous",
        "plan": [],
        "current_step_index": 0,
        "completed_steps": [],
        "stage_states": {"s1": "not_run", "s2": "not_run"},
        "pending_clarification": None,
        "final_status": "running",
        "retry_count": 0,
        "db": None,
        "stream_events": [],
    }
    state.update(overrides)
    return state


VALID_PLAN_RESPONSE = json.dumps(
    {
        "plan": [
            {
                "step": 1,
                "tool": "run_s1_assessment",
                "reasoning": "Start with migration assessment as S1 is not run yet",
                "required_inputs": {},
            },
            {
                "step": 2,
                "tool": "run_s2_complexity",
                "reasoning": "Assess complexity after S1 baseline is established",
                "required_inputs": {},
            },
        ],
        "goal_summary": "Run full RPA migration assessment for Invoice Processing",
    }
)

DONE_EVAL_RESPONSE = json.dumps(
    {
        "decision": "done",
        "reasoning": "All planned steps completed successfully — goal achieved",
        "clarification_question": None,
    }
)

CONTINUE_EVAL_RESPONSE = json.dumps(
    {
        "decision": "continue",
        "reasoning": "Step succeeded, moving to next",
        "clarification_question": None,
    }
)


# ---------------------------------------------------------------------------
# Test 1 — plan_node generates a plan from a valid LLM response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_node_generates_plan():
    state = _base_state()

    with patch("agents.project_orchestrator.get_default_manager") as mock_manager_fn:
        mock_manager = mock_manager_fn.return_value
        mock_manager.complete_async = AsyncMock(return_value=VALID_PLAN_RESPONSE)

        result = await plan_node(state)

    assert len(result["plan"]) == 2
    assert result["plan"][0]["tool"] == "run_s1_assessment"
    assert result["plan"][1]["tool"] == "run_s2_complexity"
    assert result["current_step_index"] == 0
    # An event should have been emitted
    assert any(e["type"] == "thinking" for e in result["stream_events"])


# ---------------------------------------------------------------------------
# Test 2 — evaluate_node returns final_status=complete when LLM says "done"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_node_returns_done():
    state = _base_state(
        plan=[{"step": 1, "tool": "run_s1_assessment", "reasoning": "x", "required_inputs": {}}],
        current_step_index=0,
        completed_steps=[
            {
                "step": 1,
                "tool": "run_s1_assessment",
                "result": {"status": "complete"},
                "status": "success",
            }
        ],
    )

    with patch("agents.project_orchestrator.get_default_manager") as mock_manager_fn:
        mock_manager = mock_manager_fn.return_value
        mock_manager.complete_async = AsyncMock(return_value=DONE_EVAL_RESPONSE)

        result = await evaluate_node(state)

    assert result["final_status"] == "complete"
    assert any(e["type"] == "decision" for e in result["stream_events"])


# ---------------------------------------------------------------------------
# Test 3 — route_after_evaluate returns "done" when final_status is "complete"
# ---------------------------------------------------------------------------


def test_route_after_evaluate_done():
    state = _base_state(final_status="complete")
    assert route_after_evaluate(state) == "done"


def test_route_after_evaluate_done_on_failed():
    state = _base_state(final_status="failed")
    assert route_after_evaluate(state) == "done"


# ---------------------------------------------------------------------------
# Test 4 — route_after_evaluate returns "execute" when no failures and running
# ---------------------------------------------------------------------------


def test_route_after_evaluate_execute():
    state = _base_state(
        final_status="running",
        completed_steps=[
            {
                "step": 1,
                "tool": "run_s1_assessment",
                "result": {"status": "complete"},
                "status": "success",
            }
        ],
    )
    assert route_after_evaluate(state) == "execute"


# ---------------------------------------------------------------------------
# Bonus — route_after_evaluate returns "needs_input" when status is needs_input
# ---------------------------------------------------------------------------


def test_route_after_evaluate_needs_input():
    state = _base_state(
        final_status="needs_input",
        pending_clarification="What start date should we use?",
    )
    assert route_after_evaluate(state) == "needs_input"


# ---------------------------------------------------------------------------
# Bonus — route_after_evaluate returns "retry" on first failure
# ---------------------------------------------------------------------------


def test_route_after_evaluate_retry_on_first_failure():
    state = _base_state(
        final_status="running",
        retry_count=1,
        completed_steps=[
            {
                "step": 1,
                "tool": "run_s1_assessment",
                "result": {"error": "timeout"},
                "status": "failed",
            }
        ],
    )
    assert route_after_evaluate(state) == "retry"


# ---------------------------------------------------------------------------
# Bonus — route_after_evaluate returns "revise_plan" after retry_count reset
# ---------------------------------------------------------------------------


def test_route_after_evaluate_revise_plan_after_max_retries():
    state = _base_state(
        final_status="running",
        retry_count=0,  # was reset from ≥2 by evaluate_node
        completed_steps=[
            {
                "step": 1,
                "tool": "run_s1_assessment",
                "result": {"error": "persistent failure"},
                "status": "failed",
            }
        ],
    )
    assert route_after_evaluate(state) == "revise_plan"
