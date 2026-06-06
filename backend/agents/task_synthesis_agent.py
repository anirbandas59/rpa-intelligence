"""
Task Synthesis Agent (Stage 3 Job B) - NEW for Phase 3.

Synthesizes task_extraction from S2 process_summary when no document uploaded.
Uses LangGraph StateGraph with Reflexion validation loop.

Pattern: synthesize → validate → reflect → correct (up to 2 reflexion retries)
"""

import json
import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from core.exceptions import AgentExecutionError, LLMProviderError
from llm.manager import get_default_manager
from prompts.task_synthesis_prompts import (
    REFLEXION_SYNTHESIS_SYSTEM,
    REFLEXION_SYNTHESIS_USER,
    TASK_SYNTHESIS_SYSTEM,
    TASK_SYNTHESIS_USER,
)

logger = logging.getLogger(__name__)


class SynthesisState(TypedDict):
    """State for task synthesis with reflexion support."""

    session_id: str
    use_case_id: str
    process_summary: dict
    total_effort_hours: float
    complexity_class: str
    raw_synthesis: dict | None
    validated_synthesis: dict | None
    validation_errors: list[str]
    reflexion_count: int
    error: str | None
    result: dict | None


def _parse_synthesis_json(response: str) -> dict:
    """Parse LLM JSON response, handling markdown fences."""
    text = response.strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise AgentExecutionError(f"No JSON object found in response: {response[:200]}")

    json_text = text[start : end + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise AgentExecutionError(f"Failed to parse JSON: {e}. Text: {json_text[:200]}")


async def synthesize_tasks_node(state: SynthesisState) -> dict:
    """
    Node 1: Initial synthesis - expand key_activities into detailed steps with hours.
    """
    logger.info(
        f"[task_synthesis] synthesize_tasks_node attempt={state.get('reflexion_count', 0) + 1} "
        f"use_case={state['use_case_id']} budget={state['total_effort_hours']}h"
    )

    process_summary = state["process_summary"]
    total_effort_hours = state["total_effort_hours"]
    complexity_class = state["complexity_class"]

    llm = get_default_manager()
    system_prompt = TASK_SYNTHESIS_SYSTEM
    user_prompt = TASK_SYNTHESIS_USER.format(
        process_summary_json=json.dumps(process_summary, indent=2),
        total_effort_hours=total_effort_hours,
        complexity_class=complexity_class,
    )

    try:
        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=2000,
            temperature=0.3,
            model="claude-sonnet-4-5",  # Use Sonnet for synthesis (more capable)
        )
    except Exception as e:
        raise LLMProviderError(f"Task synthesis LLM call failed: {e}")

    try:
        synthesis_data = _parse_synthesis_json(response)
    except AgentExecutionError:
        raise

    logger.info(
        f"[task_synthesis] Synthesis generated: {len(synthesis_data.get('activities', []))} activities"
    )

    return {
        **state,
        "raw_synthesis": synthesis_data,
    }


def validate_synthesis_node(state: SynthesisState) -> dict:
    """
    Node 2: Reflexion validation - check multiple constraints.

    Checks:
    1. Hour sum: Σ(step hours where reusability != "full") == total_effort_hours (±0.5h)
    2. Context relevance: Activities match process domain (inferred from summary)
    3. Completeness: Each key_activity represented in synthesis
    4. Reusability logic: "full" reusability only for genuinely reusable components
    """
    logger.info(
        f"[task_synthesis] validate_synthesis_node reflexion_count={state.get('reflexion_count', 0)}"
    )

    synthesis = state.get("raw_synthesis")
    if not synthesis:
        return {**state, "validation_errors": ["No synthesis data"]}

    process_summary = state["process_summary"]
    total_effort_hours = state["total_effort_hours"]
    errors = []

    # Check 1: Hour sum validation
    activities = synthesis.get("activities", [])
    total_hours = 0.0

    for activity in activities:
        for step in activity.get("steps", []):
            weight_hours = step.get("weight_hours", 0.0)
            reusability = step.get("reusability", "none")

            # Calculate net hours based on reusability
            if reusability == "full":
                net_hours = 0.0
            elif reusability == "partial":
                net_hours = weight_hours * 0.5
            else:  # none
                net_hours = weight_hours

            total_hours += net_hours

    hour_diff = abs(total_hours - total_effort_hours)
    if hour_diff > 0.5:
        errors.append(
            f"Hour sum mismatch: expected {total_effort_hours}h, got {total_hours}h (diff: {hour_diff:.1f}h)"
        )

    # Check 2: Context relevance
    key_applications = process_summary.get("key_applications", [])
    key_technologies = process_summary.get("key_additional_technologies", [])

    # Infer process type
    has_web = any(
        "browser" in app.lower() or "web" in app.lower() or "http" in tech.lower()
        for app in key_applications
        for tech in key_technologies
    )

    # Check for irrelevant web activities in non-web automation
    if not has_web:
        for activity in activities:
            activity_name = activity.get("name", "").lower()
            for step in activity.get("steps", []):
                step_desc = step.get("description", "").lower()
                if any(
                    keyword in activity_name or keyword in step_desc
                    for keyword in ["login to web", "navigate web", "browser", "url"]
                ):
                    errors.append(
                        f"Context mismatch: Found web activity '{step_desc}' but process has no web applications"
                    )
                    break

    # Check 3: Completeness - each key_activity should appear
    key_activities = process_summary.get("key_activities", [])
    synthesis_activity_names = [act.get("name", "").lower() for act in activities]

    for key_act in key_activities[:5]:  # Check first 5 key activities
        key_act_lower = key_act.lower()
        # Check if any synthesis activity is related (substring match)
        if not any(
            key_act_lower in synth_name or synth_name in key_act_lower
            for synth_name in synthesis_activity_names
        ):
            errors.append(f"Completeness: Key activity '{key_act}' not represented in synthesis")

    # Check 4: Reusability abuse - warn if >30% of steps marked as full reusability
    total_steps = sum(len(act.get("steps", [])) for act in activities)
    full_reusability_steps = sum(
        1
        for act in activities
        for step in act.get("steps", [])
        if step.get("reusability") == "full"
    )

    if total_steps > 0 and (full_reusability_steps / total_steps) > 0.3:
        errors.append(
            f"Reusability abuse: {full_reusability_steps}/{total_steps} steps marked as 'full' reusability (>30%)"
        )

    if errors:
        logger.warning(f"[task_synthesis] Validation failed: {errors}")
        return {
            **state,
            "validation_errors": errors,
        }

    logger.info("[task_synthesis] Validation passed")
    return {
        **state,
        "validated_synthesis": synthesis,
        "validation_errors": [],
    }


async def reflexion_correct_node(state: SynthesisState) -> dict:
    """
    Node 3: Reflexion correction - invoke LLM with validation errors for self-correction.
    """
    logger.info(
        f"[task_synthesis] reflexion_correct_node attempt={state['reflexion_count']} "
        f"errors={len(state.get('validation_errors', []))}"
    )

    validation_errors = "\n".join(f"- {err}" for err in state.get("validation_errors", []))

    system_prompt = REFLEXION_SYNTHESIS_SYSTEM.format(validation_errors=validation_errors)

    user_prompt = REFLEXION_SYNTHESIS_USER.format(
        original_synthesis=json.dumps(state.get("raw_synthesis", {}), indent=2),
        process_summary_json=json.dumps(state["process_summary"], indent=2),
        total_effort_hours=state["total_effort_hours"],
    )

    llm = get_default_manager()

    try:
        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=2000,
            temperature=0.3,
            model="claude-sonnet-4-5",
        )
    except Exception as e:
        logger.error(f"[task_synthesis] Reflexion LLM call failed: {e}")
        # Fall back to original synthesis
        return state

    try:
        corrected_synthesis = _parse_synthesis_json(response)
        logger.info("[task_synthesis] Reflexion correction applied")

        return {
            **state,
            "raw_synthesis": corrected_synthesis,
            "reflexion_count": state.get("reflexion_count", 0) + 1,
            "validation_errors": [],
        }
    except AgentExecutionError as e:
        logger.error(f"[task_synthesis] Failed to parse reflexion correction: {e}")
        return state


def store_synthesis_node(state: SynthesisState) -> dict:
    """
    Node 4: Store validated synthesis as final result.
    """
    logger.info("[task_synthesis] store_synthesis_node")

    validated = state.get("validated_synthesis")
    if not validated:
        raise AgentExecutionError("No validated synthesis available")

    # Add metadata
    result = {
        **validated,
        "extraction_status": "synthesized",
        "source": "s2_summary",
        "verification_passed": True,
        "reflexion_iterations": state.get("reflexion_count", 0),
    }

    logger.info(
        f"[task_synthesis] Synthesis complete: {len(result['activities'])} activities, "
        f"{result['total_net_hours']}h total"
    )

    return {
        **state,
        "result": result,
        "error": None,
    }


def route_validation(state: SynthesisState) -> str:
    """Route after validation: correct if errors and retries remain, else store."""
    if state.get("validation_errors") and state.get("reflexion_count", 0) < 2:
        return "correct"
    elif state.get("validated_synthesis"):
        return "store"
    else:
        # Validation failed after max retries
        return "store"  # Store best effort


def _build_synthesis_graph():
    """Build and compile the task synthesis LangGraph StateGraph with reflexion."""
    workflow = StateGraph(SynthesisState)

    workflow.add_node("synthesize_tasks", synthesize_tasks_node)
    workflow.add_node("validate_synthesis", validate_synthesis_node)
    workflow.add_node("reflexion_correct", reflexion_correct_node)
    workflow.add_node("store_synthesis", store_synthesis_node)

    workflow.set_entry_point("synthesize_tasks")
    workflow.add_edge("synthesize_tasks", "validate_synthesis")
    workflow.add_conditional_edges(
        "validate_synthesis",
        route_validation,
        {
            "correct": "reflexion_correct",
            "store": "store_synthesis",
        },
    )
    # After correction, loop back to validate again
    workflow.add_edge("reflexion_correct", "validate_synthesis")
    workflow.add_edge("store_synthesis", END)

    return workflow.compile()


async def synthesize_task_extraction(
    use_case_id: str,
    process_summary: dict,
    total_effort_hours: float,
    complexity_class: str,
    session_id: str,
) -> dict:
    """
    Synthesize task_extraction from S2 process_summary when no document available.

    Public entry point for Stage 3 Job B synthesis.

    Args:
        use_case_id: UseCase ID
        process_summary: Process summary from S2 (with key_activities, etc.)
        total_effort_hours: Budget in hours (effort_weeks * 40)
        complexity_class: XS|S|M|L|XL
        session_id: Session/run ID for logging

    Returns:
        dict with structure matching task_extraction_agent output:
        {
            "extraction_status": "synthesized",
            "source": "s2_summary",
            "activities": [...],
            "total_net_hours": float,
            "verification_passed": bool,
            "reflexion_iterations": int
        }

    Raises:
        LLMProviderError: If LLM calls fail
        AgentExecutionError: If synthesis cannot be completed
    """
    logger.info(
        f"[task_synthesis] Starting synthesis: use_case={use_case_id} "
        f"budget={total_effort_hours}h class={complexity_class}"
    )

    graph = _build_synthesis_graph()
    initial_state: SynthesisState = {
        "session_id": session_id,
        "use_case_id": use_case_id,
        "process_summary": process_summary,
        "total_effort_hours": total_effort_hours,
        "complexity_class": complexity_class,
        "raw_synthesis": None,
        "validated_synthesis": None,
        "validation_errors": [],
        "reflexion_count": 0,
        "error": None,
        "result": None,
    }

    final_state = await graph.ainvoke(initial_state)

    if final_state.get("result") is None:
        raise AgentExecutionError(
            f"Task synthesis failed: {final_state.get('error', 'unknown error')}"
        )

    return final_state["result"]
