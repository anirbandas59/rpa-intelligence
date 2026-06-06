"""
Stage 4 tracker agent — WBS grouping + date sequencing.
LangGraph StateGraph:
  group_steps → validate_sum → sequence_dates → store_result → END
       ↑              |
       └── retry ←────┘ (if sum mismatch, max 2 attempts)
"""

import json
import logging
from datetime import date
from typing import TypedDict

from langgraph.graph import END, StateGraph

from core.exceptions import AgentExecutionError, LLMProviderError
from llm.manager import get_default_manager
from prompts.tracker_prompts import S4_GROUP_STEPS_SYSTEM, S4_GROUP_STEPS_USER
from tools.output.tracker_sequencer import SequencerInput, TrackerRow, sequence_dates

logger = logging.getLogger(__name__)


class TrackerState(TypedDict):
    """State for tracker agent."""

    session_id: str  # MANDATORY per rule 7
    use_case_id: str
    process_name: str
    task_extraction: dict  # Activities/steps from Stage 3 Job A
    total_effort_hours: float
    complexity_class: str
    effort_weeks: int
    build_sit_window: dict  # {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
    sprint_count: int  # KEEP for backward compat (tool registry still uses it)
    sprint_capacity: int  # KEEP for backward compat
    raw_llm_response: str
    wbs_rows: list[dict]  # Replaced extracted_features
    sequenced_rows: list[dict]  # Replaced sprint_assignment
    error: str | None
    retry_count: int
    retry_hint: str | None


async def group_steps_node(state: TrackerState) -> dict:
    """
    Node 1: Call Sonnet to group task extraction steps into WBS rows.
    When retry_hint is set, appends correction hint to the user prompt.
    """
    session_id = state["session_id"]
    retry_count = state.get("retry_count", 0)

    logger.info(
        "group_steps_node entered",
        extra={"session_id": session_id, "node": "group_steps", "attempt": retry_count + 1}
    )

    try:
        llm = get_default_manager()

        # Convert task_extraction dict to JSON string for prompt
        task_extraction_json = json.dumps(state["task_extraction"], indent=2)

        system_prompt = S4_GROUP_STEPS_SYSTEM.format(
            total_effort_hours=state["total_effort_hours"]
        )

        user_prompt = S4_GROUP_STEPS_USER.format(
            task_extraction_json=task_extraction_json,
            total_effort_hours=state["total_effort_hours"],
            process_name=state["process_name"],
        )

        if state.get("retry_hint"):
            user_prompt += (
                f"\n\nPrevious attempt failed validation: {state['retry_hint']}. "
                f"Please correct the hour grouping and retry."
            )
            logger.info(
                f"Retrying with hint: {state['retry_hint']}",
                extra={"session_id": session_id}
            )

        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=2000,
            temperature=0.4,
        )

        logger.info(
            f"Received LLM response ({len(response)} chars)",
            extra={"session_id": session_id}
        )

        return {"raw_llm_response": response}

    except Exception as e:
        error_msg = f"WBS grouping LLM call failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"error": error_msg}


def validate_sum_node(state: TrackerState) -> dict:
    """
    Node 2: Parse response and validate hour sum.
    On success: routes to sequence_dates.
    On failure with retries remaining: routes to group_steps with retry_hint.
    On failure without retries: sets error.
    """
    session_id = state["session_id"]
    logger.info("validate_sum_node entered", extra={"session_id": session_id, "node": "validate_sum"})

    try:
        # Parse JSON response
        cleaned = state["raw_llm_response"].strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        # Find JSON object
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            raise LLMProviderError("No JSON object found in LLM response")

        json_str = cleaned[start_idx:end_idx]
        parsed = json.loads(json_str)

        # Validate structure
        if "wbs_rows" not in parsed:
            raise LLMProviderError("Missing 'wbs_rows' key in LLM response")

        wbs_rows = parsed["wbs_rows"]

        # Validate hour sum
        budget = state["total_effort_hours"]
        actual_sum = sum(row.get("hours", 0) for row in wbs_rows)
        diff = abs(actual_sum - budget)
        tolerance = 0.5

        if diff <= tolerance:
            # Success
            logger.info(
                f"Hour sum validation passed: {actual_sum:.2f}h / {budget:.2f}h",
                extra={"session_id": session_id}
            )
            return {"wbs_rows": wbs_rows, "error": None}

        else:
            # Validation failed
            attempts = state.get("retry_count", 0) + 1

            if attempts >= 2:
                error_msg = (
                    f"Hour sum validation failed after {attempts} attempts. "
                    f"Expected {budget:.2f}h but got {actual_sum:.2f}h"
                )
                logger.error(error_msg, extra={"session_id": session_id})
                return {"error": error_msg, "retry_count": attempts}
            else:
                retry_hint = (
                    f"The total hours was {actual_sum:.2f} "
                    f"but must equal {budget:.2f}. Regroup the steps to match."
                )
                logger.warning(
                    f"Retrying WBS grouping (attempt {attempts}/2)",
                    extra={"session_id": session_id}
                )
                return {
                    "retry_count": attempts,
                    "retry_hint": retry_hint,
                    "error": None,
                }

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse WBS JSON response: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"WBS validation failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"error": error_msg}


def should_retry(state: TrackerState) -> str:
    """
    Routing function: determines if we should retry or proceed/fail.
    """
    if state.get("error"):
        return "end"

    if state.get("wbs_rows"):
        return "sequence_dates"

    # Validation failed but we can retry
    if state.get("retry_count", 0) < 2:
        return "group_steps"

    return "end"


def sequence_dates_node(state: TrackerState) -> dict:
    """
    Node 3: Assign sequential dates using deterministic sequencer.
    """
    session_id = state["session_id"]
    logger.info("sequence_dates_node entered", extra={"session_id": session_id, "node": "sequence_dates"})

    try:
        # Convert wbs_rows to TrackerRow objects
        tracker_rows = [
            TrackerRow(
                feature=row["feature"],
                hours=row["hours"],
                priority=row["priority"],
            )
            for row in state["wbs_rows"]
        ]

        # Parse build_sit_window dates
        build_sit_start = date.fromisoformat(state["build_sit_window"]["start_date"])
        build_sit_end = date.fromisoformat(state["build_sit_window"]["end_date"])

        # Run sequencer
        sequencer_input = SequencerInput(
            tracker_rows=tracker_rows,
            build_sit_start=build_sit_start,
            build_sit_end=build_sit_end,
            total_effort_hours=state["total_effort_hours"],
        )

        sequenced = sequence_dates(sequencer_input)

        # Convert to dict for storage
        sequenced_rows = [
            {
                "feature": row.feature,
                "hours": row.hours,
                "priority": row.priority,
                "start_date": row.start_date.isoformat(),
                "end_date": row.end_date.isoformat(),
            }
            for row in sequenced
        ]

        logger.info(
            f"Date sequencing complete: {len(sequenced_rows)} rows",
            extra={"session_id": session_id}
        )

        return {"sequenced_rows": sequenced_rows}

    except Exception as e:
        error_msg = f"Date sequencing failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"error": error_msg}


def store_result_node(state: TrackerState) -> dict:
    """
    Node 4: Result stored successfully (actual DB write happens in API handler).
    """
    session_id = state["session_id"]
    logger.info("store_result_node entered", extra={"session_id": session_id, "node": "store_result"})
    logger.info(
        f"Tracker agent complete for use case {state['use_case_id']}",
        extra={"session_id": session_id}
    )
    return {}


def build_tracker_graph() -> StateGraph:
    """Build and compile the tracker agent StateGraph."""
    workflow = StateGraph(TrackerState)

    # Add nodes
    workflow.add_node("group_steps", group_steps_node)
    workflow.add_node("validate_sum", validate_sum_node)
    workflow.add_node("sequence_dates", sequence_dates_node)
    workflow.add_node("store_result", store_result_node)

    # Define edges
    workflow.set_entry_point("group_steps")
    workflow.add_edge("group_steps", "validate_sum")
    workflow.add_conditional_edges(
        "validate_sum",
        should_retry,
        {
            "group_steps": "group_steps",
            "sequence_dates": "sequence_dates",
            "end": END,
        },
    )
    workflow.add_edge("sequence_dates", "store_result")
    workflow.add_edge("store_result", END)

    return workflow.compile()


# Keep backward-compat alias
create_tracker_graph = build_tracker_graph


async def run_tracker_agent(
    use_case_id: str,
    process_name: str,
    task_extraction: dict,
    total_effort_hours: float,
    build_sit_window: dict,
    complexity_class: str,
    effort_weeks: int,
    session_id: str,
    sprint_count: int = 0,  # DEPRECATED but kept for backward compat
    sprint_capacity: int = 8,  # DEPRECATED but kept for backward compat
) -> dict:
    """
    Run the tracker agent to group steps and assign dates.

    Args:
        use_case_id: Use case ID
        process_name: Process name
        task_extraction: Task extraction result from Stage 3 Job A
        total_effort_hours: Total effort budget
        build_sit_window: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
        complexity_class: Complexity classification
        effort_weeks: Total effort in weeks
        session_id: Session ID for logging
        sprint_count: DEPRECATED - kept for backward compat
        sprint_capacity: DEPRECATED - kept for backward compat

    Returns:
        dict with wbs_rows, sequenced_rows, and metadata
    """
    logger.info(
        f"Starting tracker agent for use case {use_case_id}",
        extra={"session_id": session_id}
    )

    initial_state: TrackerState = {
        "session_id": session_id,
        "use_case_id": use_case_id,
        "process_name": process_name,
        "task_extraction": task_extraction,
        "total_effort_hours": total_effort_hours,
        "complexity_class": complexity_class,
        "effort_weeks": effort_weeks,
        "build_sit_window": build_sit_window,
        "sprint_count": sprint_count,
        "sprint_capacity": sprint_capacity,
        "raw_llm_response": "",
        "wbs_rows": [],
        "sequenced_rows": [],
        "error": None,
        "retry_count": 0,
        "retry_hint": None,
    }

    graph = build_tracker_graph()

    try:
        final_state = await graph.ainvoke(initial_state)

        if final_state.get("error"):
            raise AgentExecutionError(final_state["error"])

        if not final_state.get("sequenced_rows"):
            raise AgentExecutionError("Tracker agent completed but no sequenced rows generated")

        result = {
            "wbs_rows": final_state["wbs_rows"],
            "sequenced_rows": final_state["sequenced_rows"],
            "raw_llm_response": final_state["raw_llm_response"],
            "metadata": {
                "complexity_class": complexity_class,
                "effort_weeks": effort_weeks,
                "total_hours": total_effort_hours,
                "total_rows": len(final_state["sequenced_rows"]),
                "retry_count": final_state.get("retry_count", 0),
            },
        }

        logger.info(
            f"Tracker agent completed successfully for use case {use_case_id}",
            extra={"session_id": session_id}
        )
        return result

    except Exception as e:
        logger.error(f"Tracker agent failed: {e}", extra={"session_id": session_id})
        raise AgentExecutionError(f"Tracker agent failed: {e}")
