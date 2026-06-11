"""
Unified Task Decomposition Agent (Stage 3 Job A).

Replaces task_extraction_agent.py and task_synthesis_agent.py.
Handles both extraction (from document) and synthesis (from S2 summary).

LangGraph StateGraph:
  determine_source → [extract_from_document OR synthesize_from_summary]
                   → validate_structure → validate_hour_sum
                   → validate_context_relevance → store_result → END
                                  |
                                  └── reflexion_correct (max 2 retries per validation type)
"""

import json
import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langsmith import traceable

from config.settings import get_settings
from core.exceptions import AgentExecutionError, LLMProviderError
from llm.manager import get_stage_manager
from prompts.task_extraction_prompts import TASK_EXTRACTION_SYSTEM, TASK_EXTRACTION_USER
from prompts.task_synthesis_prompts import (
    REFLEXION_SYNTHESIS_SYSTEM,
    REFLEXION_SYNTHESIS_USER,
    TASK_SYNTHESIS_SYSTEM,
    TASK_SYNTHESIS_USER,
)
from tools.analysis.task_extraction_tool import (
    TaskExtractionResult,
    parse_task_extraction,
    validate_hour_sum,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class TaskDecompositionState(TypedDict, total=False):
    """State for unified task decomposition agent."""

    # Inputs
    session_id: str
    use_case_id: str
    total_effort_hours: float
    complexity_class: str

    # Data sources (one must be present)
    document_text: str | None
    process_summary: dict | None

    # Processing
    source_type: str  # "document" | "s2_summary"
    raw_llm_response: str
    parsed_activities: list[dict]
    validation_errors: list[str]
    retry_count: int
    current_validation_stage: str  # "structure" | "hour_sum" | "context_relevance"

    # Output
    task_extraction: dict | None

    # Status
    status: str  # "running" | "complete" | "failed"
    errors: list[str]


def determine_source_node(state: TaskDecompositionState) -> dict:
    """
    Node 1: Determine data source and set source_type.
    """
    session_id = state.get("session_id", "task_decomposition")

    if state.get("document_text"):
        source_type = "document"
        logger.info(
            "Source determined: document extraction",
            extra={"session_id": session_id, "node": "determine_source"},
        )
    elif state.get("process_summary"):
        source_type = "s2_summary"
        logger.info(
            "Source determined: S2 summary synthesis",
            extra={"session_id": session_id, "node": "determine_source"},
        )
    else:
        error_msg = "No data source available (document_text or process_summary required)"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"status": "failed", "errors": [error_msg]}

    return {"source_type": source_type, "current_validation_stage": "structure"}


def route_source(state: TaskDecompositionState) -> str:
    """Routing: go to extraction or synthesis based on source_type."""
    if state.get("status") == "failed":
        return "end"

    if state.get("source_type") == "document":
        return "extract_from_document"
    else:
        return "synthesize_from_summary"


async def extract_from_document_node(state: TaskDecompositionState) -> dict:
    """
    Node 2a: Extract tasks from document using task_extraction prompts.
    """
    session_id = state.get("session_id", "task_decomposition")
    retry_count = state.get("retry_count", 0)

    logger.info(
        f"extract_from_document_node attempt={retry_count + 1}",
        extra={"session_id": session_id, "node": "extract_from_document"},
    )

    if state.get("status") == "failed":
        return {}

    try:
        llm = get_stage_manager("s3_task_extraction")

        total_effort_hours = state["total_effort_hours"]
        hour_tolerance_pct = settings.hour_tolerance_percentage
        hour_tolerance = total_effort_hours * (hour_tolerance_pct / 100.0)
        hour_tolerance_min = total_effort_hours - hour_tolerance
        hour_tolerance_max = total_effort_hours + hour_tolerance

        system_prompt = TASK_EXTRACTION_SYSTEM.format(total_effort_hours=total_effort_hours)

        # Build process context from S2 summary
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
            document_text=state.get("document_text", ""),
            process_context=process_context,
            total_effort_hours=total_effort_hours,
            hour_tolerance=hour_tolerance,
            hour_tolerance_percentage=hour_tolerance_pct,
            hour_tolerance_min=hour_tolerance_min,
            hour_tolerance_max=hour_tolerance_max,
            process_name=state.get("use_case_id", "Unknown"),
        )

        # Add retry hint if retrying
        if retry_count > 0 and state.get("validation_errors"):
            user_prompt += (
                f"\n\nPrevious attempt failed validation:\n"
                f"{', '.join(state['validation_errors'])}\n"
                f"Please correct these issues and retry."
            )

        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=3000,
            temperature=0.3 + (retry_count * 0.1),  # Increase temp on retries
        )

        logger.info(
            f"Received extraction response ({len(response)} chars)",
            extra={"session_id": session_id},
        )

        return {"raw_llm_response": response}

    except Exception as e:
        error_msg = f"Document extraction LLM call failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        errors = state.get("errors", [])
        errors.append(error_msg)
        return {"status": "failed", "errors": errors}


async def synthesize_from_summary_node(state: TaskDecompositionState) -> dict:
    """
    Node 2b: Synthesize tasks from S2 process_summary using task_synthesis prompts.
    """
    session_id = state.get("session_id", "task_decomposition")
    retry_count = state.get("retry_count", 0)

    logger.info(
        f"synthesize_from_summary_node attempt={retry_count + 1}",
        extra={"session_id": session_id, "node": "synthesize_from_summary"},
    )

    if state.get("status") == "failed":
        return {}

    try:
        llm = get_stage_manager("s3_task_synthesis")

        total_effort_hours = state["total_effort_hours"]
        hour_tolerance_pct = settings.hour_tolerance_percentage
        hour_tolerance = total_effort_hours * (hour_tolerance_pct / 100.0)
        hour_tolerance_min = total_effort_hours - hour_tolerance
        hour_tolerance_max = total_effort_hours + hour_tolerance

        system_prompt = TASK_SYNTHESIS_SYSTEM
        user_prompt = TASK_SYNTHESIS_USER.format(
            process_summary_json=json.dumps(state.get("process_summary", {}), indent=2),
            total_effort_hours=total_effort_hours,
            hour_tolerance=hour_tolerance,
            hour_tolerance_percentage=hour_tolerance_pct,
            hour_tolerance_min=hour_tolerance_min,
            hour_tolerance_max=hour_tolerance_max,
            complexity_class=state.get("complexity_class", "M"),
        )

        # Add retry hint if retrying
        if retry_count > 0 and state.get("validation_errors"):
            user_prompt += (
                f"\n\nPrevious attempt failed validation:\n"
                f"{', '.join(state['validation_errors'])}\n"
                f"Please correct these issues and retry."
            )

        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=2500,
            temperature=0.3 + (retry_count * 0.1),
        )

        logger.info(
            f"Received synthesis response ({len(response)} chars)",
            extra={"session_id": session_id},
        )

        return {"raw_llm_response": response}

    except Exception as e:
        error_msg = f"Summary synthesis LLM call failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})
        errors = state.get("errors", [])
        errors.append(error_msg)
        return {"status": "failed", "errors": errors}


def validate_structure_node(state: TaskDecompositionState) -> dict:
    """
    Node 3: Parse JSON and validate structure.
    """
    session_id = state.get("session_id", "task_decomposition")
    logger.info("validate_structure_node entered", extra={"session_id": session_id})

    if state.get("status") == "failed":
        return {}

    try:
        # Parse the LLM response
        result: TaskExtractionResult = parse_task_extraction(state.get("raw_llm_response", ""))

        logger.info(
            f"Parsed {len(result.activities)} activities with {sum(len(a.steps) for a in result.activities)} steps",
            extra={"session_id": session_id},
        )

        # Convert to dict for storage
        parsed_activities = [
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
        ]

        return {
            "parsed_activities": parsed_activities,
            "current_validation_stage": "hour_sum",
            "validation_errors": [],
        }

    except Exception as e:
        error_msg = f"Structure validation failed: {e}"
        logger.error(error_msg, extra={"session_id": session_id})

        retry_count = state.get("retry_count", 0)
        if retry_count >= 2:
            errors = state.get("errors", [])
            errors.append(error_msg)
            return {"status": "failed", "errors": errors}
        else:
            return {
                "validation_errors": [error_msg],
                "retry_count": retry_count + 1,
            }


def validate_hour_sum_node(state: TaskDecompositionState) -> dict:
    """
    Node 4: Validate hour sum with configurable tolerance.
    """
    session_id = state.get("session_id", "task_decomposition")
    logger.info("validate_hour_sum_node entered", extra={"session_id": session_id})

    if state.get("status") == "failed":
        return {}

    if state.get("current_validation_stage") != "hour_sum":
        return {}

    total_effort_hours = state["total_effort_hours"]
    hour_tolerance_pct = settings.hour_tolerance_percentage
    hour_tolerance = total_effort_hours * (hour_tolerance_pct / 100.0)

    # Calculate actual sum from parsed activities
    total_hours = 0.0
    for activity in state.get("parsed_activities", []):
        for step in activity.get("steps", []):
            weight_hours = step.get("weight_hours", 0.0)
            reusability = step.get("reusability", "none")

            if reusability == "full":
                net_hours = 0.0
            elif reusability == "partial":
                net_hours = weight_hours * 0.5
            else:
                net_hours = weight_hours

            total_hours += net_hours

    hour_diff = abs(total_hours - total_effort_hours)

    if hour_diff <= hour_tolerance:
        logger.info(
            f"Hour sum validation passed: {total_hours:.2f}h within ±{hour_tolerance:.2f}h of {total_effort_hours:.2f}h",
            extra={"session_id": session_id},
        )
        return {
            "current_validation_stage": "context_relevance",
            "validation_errors": [],
        }
    else:
        error_msg = (
            f"Hour sum mismatch: expected {total_effort_hours:.2f}h, got {total_hours:.2f}h "
            f"(diff: {hour_diff:.2f}h, tolerance: ±{hour_tolerance:.2f}h)"
        )
        logger.warning(error_msg, extra={"session_id": session_id})

        retry_count = state.get("retry_count", 0)
        if retry_count >= 2:
            errors = state.get("errors", [])
            errors.append(error_msg)
            return {"status": "failed", "errors": errors}
        else:
            return {
                "validation_errors": [error_msg],
                "retry_count": retry_count + 1,
                "current_validation_stage": "structure",  # Reset to re-extract
            }


def validate_context_relevance_node(state: TaskDecompositionState) -> dict:
    """
    Node 5: Validate activities align with process_summary (if available).
    """
    session_id = state.get("session_id", "task_decomposition")
    logger.info("validate_context_relevance_node entered", extra={"session_id": session_id})

    if state.get("status") == "failed":
        return {}

    if state.get("current_validation_stage") != "context_relevance":
        return {}

    process_summary = state.get("process_summary")
    if not process_summary:
        # Skip context validation if no process summary
        logger.info("No process_summary available, skipping context validation", extra={"session_id": session_id})
        return {"current_validation_stage": "complete", "validation_errors": []}

    errors = []

    # Check 1: Context relevance (web activities in non-web processes)
    key_applications = process_summary.get("key_applications", [])
    key_technologies = process_summary.get("key_additional_technologies", [])

    has_web = any(
        "browser" in app.lower() or "web" in app.lower() or "http" in tech.lower()
        for app in key_applications
        for tech in key_technologies
    )

    if not has_web:
        for activity in state.get("parsed_activities", []):
            activity_name = activity.get("name", "").lower()
            for step in activity.get("steps", []):
                step_desc = step.get("description", "").lower()
                if any(
                    keyword in activity_name or keyword in step_desc
                    for keyword in ["login to web", "navigate web", "browser", "url", "http://"]
                ):
                    errors.append(f"Context mismatch: Found web activity but process has no web applications")
                    break

    # Check 2: Completeness (key activities represented)
    key_activities = process_summary.get("key_activities", [])
    synthesis_activity_names = [act.get("name", "").lower() for act in state.get("parsed_activities", [])]

    for key_act in key_activities[:5]:  # Check first 5
        key_act_lower = key_act.lower()
        if not any(key_act_lower in synth_name or synth_name in key_act_lower for synth_name in synthesis_activity_names):
            errors.append(f"Incompleteness: Key activity '{key_act}' not represented in task breakdown")

    if errors:
        logger.warning(f"Context validation errors: {errors}", extra={"session_id": session_id})

        retry_count = state.get("retry_count", 0)
        if retry_count >= 2:
            state_errors = state.get("errors", [])
            state_errors.extend(errors)
            return {"status": "failed", "errors": state_errors}
        else:
            return {
                "validation_errors": errors,
                "retry_count": retry_count + 1,
                "current_validation_stage": "structure",  # Reset to re-extract
            }
    else:
        logger.info("Context validation passed", extra={"session_id": session_id})
        return {"current_validation_stage": "complete", "validation_errors": []}


def route_validation(state: TaskDecompositionState) -> str:
    """Routing: check if we need to retry or proceed to next validation stage."""
    if state.get("status") == "failed":
        return "end"

    current_stage = state.get("current_validation_stage", "")

    # If we have validation errors and retry count < 2, go back to source
    if state.get("validation_errors") and state.get("retry_count", 0) < 2:
        source_type = state.get("source_type", "document")
        if source_type == "document":
            return "extract_from_document"
        else:
            return "synthesize_from_summary"

    # If validation complete, store result
    if current_stage == "complete":
        return "store_result"

    # Otherwise, continue to next validation stage
    if current_stage == "structure":
        return "validate_structure"
    elif current_stage == "hour_sum":
        return "validate_hour_sum"
    elif current_stage == "context_relevance":
        return "validate_context_relevance"

    return "end"


def store_result_node(state: TaskDecompositionState) -> dict:
    """
    Node 6: Store successful result.
    """
    session_id = state.get("session_id", "task_decomposition")
    logger.info("store_result_node entered", extra={"session_id": session_id})

    # Calculate total_net_hours
    total_hours = 0.0
    for activity in state.get("parsed_activities", []):
        for step in activity.get("steps", []):
            weight_hours = step.get("weight_hours", 0.0)
            reusability = step.get("reusability", "none")

            if reusability == "full":
                net_hours = 0.0
            elif reusability == "partial":
                net_hours = weight_hours * 0.5
            else:
                net_hours = weight_hours

            total_hours += net_hours

    task_extraction = {
        "extraction_status": "complete",
        "source": state.get("source_type", "unknown"),
        "activities": state.get("parsed_activities", []),
        "total_net_hours": total_hours,
        "verification_passed": True,
        "retry_count": state.get("retry_count", 0),
    }

    logger.info(
        f"Task decomposition complete: {len(task_extraction['activities'])} activities, "
        f"{total_hours:.2f}h total",
        extra={"session_id": session_id},
    )

    return {
        "task_extraction": task_extraction,
        "status": "complete",
    }


def build_task_decomposition_graph() -> CompiledStateGraph:
    """Build and compile the unified task decomposition StateGraph."""
    workflow = StateGraph(TaskDecompositionState)

    # Add nodes
    workflow.add_node("determine_source", determine_source_node)
    workflow.add_node("extract_from_document", extract_from_document_node)
    workflow.add_node("synthesize_from_summary", synthesize_from_summary_node)
    workflow.add_node("validate_structure", validate_structure_node)
    workflow.add_node("validate_hour_sum", validate_hour_sum_node)
    workflow.add_node("validate_context_relevance", validate_context_relevance_node)
    workflow.add_node("store_result", store_result_node)

    # Define edges
    workflow.set_entry_point("determine_source")

    # Route to extraction or synthesis
    workflow.add_conditional_edges(
        "determine_source",
        route_source,
        {
            "extract_from_document": "extract_from_document",
            "synthesize_from_summary": "synthesize_from_summary",
            "end": END,
        },
    )

    # Both extraction and synthesis go to validation
    workflow.add_edge("extract_from_document", "validate_structure")
    workflow.add_edge("synthesize_from_summary", "validate_structure")

    # Validation chain with retry loops
    workflow.add_conditional_edges(
        "validate_structure",
        route_validation,
        {
            "validate_structure": "validate_structure",
            "validate_hour_sum": "validate_hour_sum",
            "extract_from_document": "extract_from_document",
            "synthesize_from_summary": "synthesize_from_summary",
            "store_result": "store_result",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "validate_hour_sum",
        route_validation,
        {
            "validate_context_relevance": "validate_context_relevance",
            "extract_from_document": "extract_from_document",
            "synthesize_from_summary": "synthesize_from_summary",
            "store_result": "store_result",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "validate_context_relevance",
        route_validation,
        {
            "store_result": "store_result",
            "extract_from_document": "extract_from_document",
            "synthesize_from_summary": "synthesize_from_summary",
            "end": END,
        },
    )

    workflow.add_edge("store_result", END)

    return workflow.compile()


# Build graph once at module level
_graph = build_task_decomposition_graph()


@traceable
async def run_task_decomposition(
    use_case_id: str,
    total_effort_hours: float,
    complexity_class: str,
    session_id: str,
    document_text: str | None = None,
    process_summary: dict | None = None,
) -> dict:
    """
    Public entry point for unified task decomposition.

    Args:
        use_case_id: Use case identifier
        total_effort_hours: Total effort budget in hours
        complexity_class: Complexity class (XS/S/M/L/XL)
        session_id: Session identifier for logging
        document_text: Optional process document text
        process_summary: Optional S2 process summary dict

    Returns:
        task_extraction dict with activities, total_net_hours, verification_passed

    Raises:
        AgentExecutionError: If decomposition fails after retries
    """
    logger.info(
        f"Starting task decomposition for use case {use_case_id}",
        extra={"session_id": session_id},
    )

    initial_state: TaskDecompositionState = {
        "session_id": session_id,
        "use_case_id": use_case_id,
        "total_effort_hours": total_effort_hours,
        "complexity_class": complexity_class,
        "document_text": document_text,
        "process_summary": process_summary,
        "source_type": "",
        "raw_llm_response": "",
        "parsed_activities": [],
        "validation_errors": [],
        "retry_count": 0,
        "current_validation_stage": "",
        "task_extraction": None,
        "status": "running",
        "errors": [],
    }

    result = await _graph.ainvoke(initial_state)

    if result.get("status") == "failed":
        errors = result.get("errors", ["Unknown error"])
        raise AgentExecutionError(f"Task decomposition failed: {'; '.join(errors)}")

    if not result.get("task_extraction"):
        raise AgentExecutionError("Task decomposition completed but no result generated")

    return result["task_extraction"]
