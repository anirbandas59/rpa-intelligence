"""
Stage 3 Job A — Task extraction agent.
LangGraph StateGraph:
  extract_tasks → validate_sum → store_result → END
                        |
                        └── correct_sum (if validation fails, max 2 retries)
"""

import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from core.exceptions import AgentExecutionError
from llm.manager import get_stage_manager
from prompts.task_extraction_prompts import TASK_EXTRACTION_SYSTEM, TASK_EXTRACTION_USER
from tools.analysis.task_extraction_tool import (
    TaskExtractionResult,
    parse_task_extraction,
    validate_hour_sum,
)

logger = logging.getLogger(__name__)


class TaskExtractionState(TypedDict):
    """State for task extraction agent."""

    session_id: str
    use_case_id: str
    document_text: str
    process_summary: dict | None  # NEW: Full process context from Stage 2
    total_effort_hours: float
    process_name: str
    raw_llm_response: str
    task_extraction: dict | None
    validation_attempts: int
    error: str | None
    retry_hint: str | None


async def extract_tasks_node(state: TaskExtractionState) -> dict:
    """
    Node 1: Call Sonnet to extract tasks with hour-sum constraint.
    """
    session_id = state["session_id"]
    validation_attempts = state.get("validation_attempts", 0)

    logger.info(
        "extract_tasks_node entered",
        extra={
            "session_id": session_id,
            "node": "extract_tasks",
            "attempt": validation_attempts + 1,
        },
    )

    try:
        llm = get_stage_manager("s3_task_extraction")

        system_prompt = TASK_EXTRACTION_SYSTEM.format(
            total_effort_hours=state["total_effort_hours"]
        )

        # Build context from process_summary if available
        process_context = ""
        if state.get("process_summary"):
            ps = state["process_summary"]
            process_context = "\n\nPROCESS CONTEXT FROM STAGE 2:\n"
            if ps.get("overall_summary"):
                process_context += f"Summary: {ps['overall_summary']}\n"
            if ps.get("key_activities"):
                process_context += f"Key Activities: {', '.join(ps['key_activities'])}\n"
            if ps.get("key_logical_points"):
                process_context += f"Business Rules: {', '.join(ps['key_logical_points'])}\n"
            if ps.get("key_applications"):
                process_context += f"Applications: {', '.join(ps['key_applications'])}\n"
            if ps.get("key_layouts"):
                process_context += f"UI Screens: {', '.join(ps['key_layouts'])}\n"
            if ps.get("key_additional_technologies"):
                process_context += f"Technologies: {', '.join(ps['key_additional_technologies'])}\n"

        user_prompt = TASK_EXTRACTION_USER.format(
            document_text=state["document_text"],
            process_context=process_context,
            total_effort_hours=state["total_effort_hours"],
            process_name=state["process_name"],
        )

        if state.get("retry_hint"):
            user_prompt += (
                f"\n\nPrevious attempt failed validation: {state['retry_hint']}. "
                f"Please rebalance the weights and retry."
            )
            logger.info(
                f"Retrying with hint: {state['retry_hint']}", extra={"session_id": session_id}
            )

        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=3000,
            temperature=0.4,
        )

        logger.info(
            f"Received LLM response ({len(response)} chars)", extra={"session_id": session_id}
        )

        return {"raw_llm_response": response}

    except Exception as e:
        error_msg = f"Task extraction LLM call failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"error": error_msg}


def validate_sum_node(state: TaskExtractionState) -> dict:
    """
    Node 2: Parse response and validate hour sum.
    On success: routes to store_result.
    On failure with retries remaining: routes to extract_tasks with retry_hint.
    On failure without retries: sets error.
    """
    session_id = state["session_id"]
    logger.info(
        "validate_sum_node entered", extra={"session_id": session_id, "node": "validate_sum"}
    )

    try:
        # Parse the response
        result: TaskExtractionResult = parse_task_extraction(state["raw_llm_response"])

        # Validate hour sum
        budget = state["total_effort_hours"]
        is_valid = validate_hour_sum(result, budget, tolerance=0.5)

        if is_valid:
            # Success - convert to dict for storage
            task_extraction_dict = {
                "extraction_status": "complete",
                "activities": [
                    {
                        "name": activity.name,
                        "steps": [
                            {
                                "description": step.description,
                                "weight_hours": step.weight_hours,
                                "reusability": step.reusability,
                            }
                            for step in activity.steps
                        ],
                    }
                    for activity in result.activities
                ],
                "total_net_hours": result.total_net_hours,
                "verification_passed": result.verification_passed,
            }

            logger.info(
                f"Hour sum validation passed: {result.total_net_hours:.2f}h / {budget:.2f}h",
                extra={"session_id": session_id},
            )

            return {"task_extraction": task_extraction_dict, "error": None}

        else:
            # Validation failed - calculate actual_sum for accurate error reporting
            actual_sum = sum(
                step.weight_hours
                for activity in result.activities
                for step in activity.steps
                if step.reusability != "full"
            )

            attempts = state.get("validation_attempts", 0) + 1

            if attempts >= 2:
                error_msg = (
                    f"Hour sum validation failed after {attempts} attempts. "
                    f"Expected {budget:.2f}h but got {actual_sum:.2f}h "
                    f"(step-level sum). LLM reported total_net_hours: {result.total_net_hours:.2f}h"
                )
                logger.error(error_msg, extra={"session_id": session_id})
                return {"error": error_msg, "validation_attempts": attempts}
            else:
                retry_hint = (
                    f"The step-level hour sum was {actual_sum:.2f}h "
                    f"but must equal {budget:.2f}h. Ensure each step has weight_hours assigned "
                    f"and the sum of all steps (where reusability != 'full') equals the budget."
                )
                logger.warning(
                    f"Retrying task extraction (attempt {attempts}/2)",
                    extra={"session_id": session_id},
                )
                return {
                    "validation_attempts": attempts,
                    "retry_hint": retry_hint,
                    "error": None,
                }

    except Exception as e:
        error_msg = f"Task extraction validation failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"error": error_msg}


def should_retry(state: TaskExtractionState) -> str:
    """
    Routing function: determines if we should retry or proceed/fail.
    """
    if state.get("error"):
        return "end"

    if state.get("task_extraction"):
        return "store_result"

    # Validation failed but we can retry
    if state.get("validation_attempts", 0) < 2:
        return "extract_tasks"

    return "end"


def store_result_node(state: TaskExtractionState) -> dict:
    """
    Node 3: Result stored successfully (actual DB write happens in API background task).
    """
    session_id = state["session_id"]
    logger.info(
        "store_result_node entered", extra={"session_id": session_id, "node": "store_result"}
    )
    logger.info(
        f"Task extraction complete for use case {state['use_case_id']}",
        extra={"session_id": session_id},
    )
    return {}


def build_task_extraction_graph() -> CompiledStateGraph[
    TaskExtractionState, None, TaskExtractionState, TaskExtractionState
]:
    """Build and compile the task extraction StateGraph."""
    workflow = StateGraph(TaskExtractionState)

    # Add nodes
    workflow.add_node("extract_tasks", extract_tasks_node)
    workflow.add_node("validate_sum", validate_sum_node)
    workflow.add_node("store_result", store_result_node)

    # Define edges
    workflow.set_entry_point("extract_tasks")
    workflow.add_edge("extract_tasks", "validate_sum")
    workflow.add_conditional_edges(
        "validate_sum",
        should_retry,
        {
            "extract_tasks": "extract_tasks",
            "store_result": "store_result",
            "end": END,
        },
    )
    workflow.add_edge("store_result", END)

    return workflow.compile()


async def run_task_extraction_agent(
    use_case_id: str,
    document_text: str,
    process_name: str,
    total_effort_hours: float,
    session_id: str,
    process_summary: dict | None = None,  # NEW: Process context from Stage 2
) -> dict:
    """
    Entry point called by background task in stage3.py.
    Returns extracted task_extraction dict on success.
    Raises AgentExecutionError on failure.
    """
    logger.info(
        f"Starting task extraction agent for use case {use_case_id}",
        extra={"session_id": session_id},
    )

    graph = build_task_extraction_graph()

    initial_state: TaskExtractionState = {
        "session_id": session_id,
        "use_case_id": use_case_id,
        "document_text": document_text,
        "process_summary": process_summary,  # NEW
        "total_effort_hours": total_effort_hours,
        "process_name": process_name,
        "raw_llm_response": "",
        "task_extraction": None,
        "validation_attempts": 0,
        "error": None,
        "retry_hint": None,
    }

    result = await graph.ainvoke(initial_state)

    if result.get("error"):
        raise AgentExecutionError(result["error"])

    if not result.get("task_extraction"):
        raise AgentExecutionError("Task extraction completed but no result was generated")

    return result["task_extraction"]
