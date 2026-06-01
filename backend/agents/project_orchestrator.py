"""
Project Orchestrator — autonomous multi-stage RPA assessment agent.

LangGraph StateGraph implementing the ReAct pattern:
  plan → execute → evaluate → [continue|retry|revise|needs_input|done]

The orchestrator uses the tool registry to invoke stage tools and Sonnet
for planning and evaluation. It supports both autonomous and supervised modes.
"""
import asyncio
import json
import logging
from typing import TypedDict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END

from core.exceptions import AgentExecutionError, LLMProviderError
from llm.manager import get_default_manager
from tools.registry import ToolRegistry
from prompts.orchestrator_prompts import (
    ORCHESTRATOR_PLAN_SYSTEM,
    ORCHESTRATOR_PLAN_USER,
    ORCHESTRATOR_EVALUATE_SYSTEM,
    ORCHESTRATOR_EVALUATE_USER,
)

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict):
    session_id: str
    use_case_id: str
    use_case_name: str
    use_case_description: str
    goal: str
    mode: str                         # autonomous | supervised
    plan: list[dict]                  # [{step, tool, reasoning, required_inputs}]
    current_step_index: int
    completed_steps: list[dict]       # [{step, tool, result, status}]
    stage_states: dict[str, str]      # {s1: complete|running|not_run, ...}
    pending_clarification: str | None
    final_status: str                 # running | complete | needs_input | failed
    retry_count: int
    db: Any                           # AsyncSession (passed through state)
    stream_events: list[dict]         # accumulated events for SSE / checkpointer


def _emit_event(state: OrchestratorState, event_type: str, content: str) -> None:
    """Append an event to state for SSE streaming and checkpointer persistence."""
    state["stream_events"].append(
        {
            "type": event_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": state["session_id"],
        }
    )
    # Non-blocking SSE publish — fire and forget so nodes stay synchronous w.r.t. state
    try:
        from api.sse_utils import publish_event

        asyncio.create_task(publish_event(state["session_id"], event_type, content))
    except RuntimeError:
        # No running event loop (e.g., tests) — skip SSE publish
        pass


def _extract_json(text: str) -> str:
    """Extract JSON object from LLM response, stripping markdown fences."""
    cleaned = text.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise LLMProviderError("No JSON object in orchestrator LLM response")
    return cleaned[start:end]


async def plan_node(state: OrchestratorState) -> OrchestratorState:
    """Generate execution plan using Sonnet."""
    logger.info(f"[orchestrator] plan_node session={state['session_id']}")

    llm = get_default_manager()
    tool_descriptions = json.dumps(ToolRegistry.list_descriptions(), indent=2)

    stage_states_str = json.dumps(state["stage_states"], indent=2)
    user_prompt = ORCHESTRATOR_PLAN_USER.format(
        goal=state["goal"],
        stage_states=stage_states_str,
        use_case_name=state["use_case_name"],
        use_case_description=state["use_case_description"],
    )
    system_prompt = ORCHESTRATOR_PLAN_SYSTEM.format(tool_descriptions=tool_descriptions)

    try:
        response = await llm.complete_async(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=1500,
            temperature=0.2,
            session_id=state["session_id"],
        )
        plan_data = json.loads(_extract_json(response))
        plan = plan_data.get("plan", [])
        logger.info(
            f"[orchestrator] Plan generated: {len(plan)} steps, session={state['session_id']}"
        )
        _emit_event(state, "thinking", f"Plan generated: {len(plan)} steps")
        return {**state, "plan": plan, "current_step_index": 0}
    except Exception as e:
        logger.error(f"[orchestrator] plan_node failed: {e}")
        raise AgentExecutionError(f"Planning failed: {e}")


async def execute_node(state: OrchestratorState) -> OrchestratorState:
    """Execute the current step from the plan using the tool registry."""
    idx = state["current_step_index"]
    if idx >= len(state["plan"]):
        logger.info(
            f"[orchestrator] No more steps to execute, session={state['session_id']}"
        )
        return {**state, "final_status": "complete"}

    step = state["plan"][idx]
    tool_name = step.get("tool", "")
    logger.info(
        f"[orchestrator] execute_node step={idx + 1}/{len(state['plan'])} tool={tool_name}"
    )
    _emit_event(state, "tool_call", f"Executing: {tool_name} (step {idx + 1})")

    try:
        tool = ToolRegistry.get(tool_name)
        inputs = dict(step.get("required_inputs", {}))
        inputs["use_case_id"] = state["use_case_id"]
        inputs["db"] = state["db"]

        result = await tool.execute(**inputs)
        result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)

        completed = {
            "step": idx + 1,
            "tool": tool_name,
            "result": result_dict,
            "status": "success",
        }
        _emit_event(state, "tool_result", f"{tool_name} → {result_dict.get('status', 'ok')}")
        logger.info(f"[orchestrator] Step {idx + 1} succeeded: {tool_name}")

        return {
            **state,
            "completed_steps": state["completed_steps"] + [completed],
            "retry_count": 0,
        }
    except Exception as e:
        logger.error(f"[orchestrator] execute_node step {idx + 1} failed: {e}")
        _emit_event(state, "error", f"{tool_name} failed: {str(e)[:100]}")
        failed = {
            "step": idx + 1,
            "tool": tool_name,
            "result": {"error": str(e)},
            "status": "failed",
        }
        return {
            **state,
            "completed_steps": state["completed_steps"] + [failed],
        }


async def evaluate_node(state: OrchestratorState) -> OrchestratorState:
    """Evaluate the last step result and decide what to do next."""
    if not state["completed_steps"]:
        return {**state, "final_status": "failed"}

    last_step = state["completed_steps"][-1]
    remaining = len(state["plan"]) - state["current_step_index"] - 1

    logger.info(
        f"[orchestrator] evaluate_node last={last_step['tool']} remaining={remaining}"
    )

    # If last step failed and we've retried 2+ times → trigger revise_plan routing
    if last_step["status"] == "failed" and state["retry_count"] >= 2:
        _emit_event(state, "decision", "Too many retries — revising plan")
        return {**state, "retry_count": 0}  # route_after_evaluate will detect this → revise_plan

    llm = get_default_manager()
    user_prompt = ORCHESTRATOR_EVALUATE_USER.format(
        step_result=json.dumps(last_step["result"]),
        step_status=last_step["status"],
        remaining_steps=remaining,
        goal=state["goal"],
    )

    try:
        response = await llm.complete_async(
            prompt=user_prompt,
            system=ORCHESTRATOR_EVALUATE_SYSTEM,
            max_tokens=500,
            temperature=0.1,
            session_id=state["session_id"],
        )
        eval_data = json.loads(_extract_json(response))
        decision = eval_data.get("decision", "continue")
        reasoning = eval_data.get("reasoning", "")
        clarification = eval_data.get("clarification_question")

        logger.info(
            f"[orchestrator] evaluate decision={decision} reason={reasoning[:80]}"
        )
        _emit_event(state, "decision", f"{decision}: {reasoning[:80]}")

        if decision == "done":
            return {**state, "final_status": "complete"}
        if decision == "needs_input":
            return {
                **state,
                "final_status": "needs_input",
                "pending_clarification": clarification,
            }
        if decision == "retry":
            return {**state, "retry_count": state["retry_count"] + 1}
        if decision == "revise_plan":
            return {**state, "retry_count": 0}
        # "continue": advance to next step
        return {**state, "current_step_index": state["current_step_index"] + 1}

    except Exception as e:
        logger.error(f"[orchestrator] evaluate_node LLM failed: {e}")
        # Default to continue on evaluation error
        return {**state, "current_step_index": state["current_step_index"] + 1}


def route_after_evaluate(state: OrchestratorState) -> str:
    """Conditional routing after evaluate_node."""
    status = state["final_status"]
    if status in ("complete", "failed"):
        return "done"
    if status == "needs_input":
        return "needs_input"

    # Detect revise_plan: last step failed AND retry_count was reset to 0
    if state["completed_steps"]:
        last = state["completed_steps"][-1]
        if last["status"] == "failed":
            if state["retry_count"] == 0:
                # retry_count was reset after ≥2 failures → revise
                return "revise_plan"
            else:
                return "retry"

    return "execute"


async def self_correct_node(state: OrchestratorState) -> OrchestratorState:
    """Revise the plan after persistent failures — routes back to plan_node."""
    logger.info(f"[orchestrator] self_correct_node session={state['session_id']}")
    _emit_event(state, "correction", "Revising plan due to failure")
    # Return state as-is; the edge back to plan_node triggers a fresh plan
    return state


async def await_input_node(state: OrchestratorState) -> OrchestratorState:
    """Pause execution waiting for user clarification. Persisted via checkpointer."""
    logger.info(
        f"[orchestrator] Awaiting user input: {state['pending_clarification']}, "
        f"session={state['session_id']}"
    )
    _emit_event(state, "needs_input", state["pending_clarification"] or "")
    # Graph terminates here; resumed via /respond endpoint which re-invokes from checkpoint
    return state


def build_orchestrator_graph():
    """Build and compile the orchestrator StateGraph."""
    workflow = StateGraph(OrchestratorState)

    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("self_correct", self_correct_node)
    workflow.add_node("await_input", await_input_node)

    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "evaluate")
    workflow.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "execute": "execute",
            "retry": "execute",
            "revise_plan": "self_correct",
            "needs_input": "await_input",
            "done": END,
        },
    )
    workflow.add_edge("self_correct", "plan")
    workflow.add_edge("await_input", END)  # pause; resume via /respond endpoint

    return workflow.compile()
