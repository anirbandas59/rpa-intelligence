"""
Stage 4 tracker agent — feature decomposition + sprint assignment.
LangGraph StateGraph:
  read_documents → decompose_features → validate_features → assign_sprints → END
                         ↑                      |
                         └── retry (max 2) ←────┘
"""

import json
import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from core.exceptions import AgentExecutionError, LLMProviderError
from core.quality import QualityEvaluator
from llm.manager import get_default_manager
from prompts.tracker_prompts import S4_DECOMPOSE_SYSTEM, S4_DECOMPOSE_USER
from tools.sprint_assigner import Feature, assign_sprints

logger = logging.getLogger(__name__)


class TrackerState(TypedDict):
    """State for tracker agent."""

    use_case_id: str
    process_name: str
    process_description: str
    complexity_class: str
    effort_weeks: int
    sprint_count: int
    sprint_capacity: int
    document_context: str
    raw_llm_response: str
    extracted_features: list[dict]
    sprint_assignment: dict
    error: str | None
    retry_count: int
    retry_hint: str | None


class FeatureDecomposition(BaseModel):
    """Pydantic model for LLM response."""

    features: list[dict]
    summary: str


def read_documents_node(state: TrackerState) -> TrackerState:
    """
    Node 1: Read process documents if available.
    For Phase 5, we'll use process_description as primary source.
    """
    logger.info(f"[tracker_agent] Reading documents for use case {state['use_case_id']}")

    # For now, use description as context
    # In full implementation, would read from UploadedFile records
    document_context = f"Process Overview: {state['process_description']}"

    state["document_context"] = document_context
    logger.info(f"[tracker_agent] Document context prepared ({len(document_context)} chars)")
    return state


async def decompose_features_node(state: TrackerState) -> TrackerState:
    """
    Node 2: Call Sonnet to decompose process into features.
    When retry_hint is set, appends correction hint to the user prompt.
    """
    retry_count = state.get("retry_count", 0)
    logger.info(
        f"[tracker_agent] decompose_features_node attempt={retry_count + 1} "
        f"process={state['process_name']}"
    )

    try:
        llm = get_default_manager()

        user_prompt = S4_DECOMPOSE_USER.format(
            process_name=state["process_name"],
            complexity_class=state["complexity_class"],
            effort_weeks=state["effort_weeks"],
            process_description=state["process_description"],
            document_context=state["document_context"],
            sprint_count=state["sprint_count"],
        )

        if state.get("retry_hint"):
            user_prompt += (
                f"\n\nPrevious attempt failed validation: {state['retry_hint']}. "
                f"Please correct and retry."
            )
            logger.info(f"[tracker_agent] Retrying with hint: {state['retry_hint']}")

        response = await llm.complete_async(
            system=S4_DECOMPOSE_SYSTEM, prompt=user_prompt, max_tokens=2000, temperature=0.4
        )

        state["raw_llm_response"] = response
        logger.info(f"[tracker_agent] Received LLM response ({len(response)} chars)")

        # Parse JSON response
        # Strip markdown fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Remove opening fence
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
        if "features" not in parsed:
            raise LLMProviderError("Missing 'features' key in LLM response")

        state["extracted_features"] = parsed["features"]
        logger.info(f"[tracker_agent] Extracted {len(parsed['features'])} features")

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse LLM JSON response: {e}"
        logger.error(f"[tracker_agent] {error_msg}")
        state["error"] = error_msg
        raise AgentExecutionError(error_msg)
    except Exception as e:
        error_msg = f"Feature decomposition failed: {e}"
        logger.error(f"[tracker_agent] {error_msg}")
        state["error"] = error_msg
        raise AgentExecutionError(error_msg)

    return state


def validate_features_node(state: TrackerState) -> TrackerState:
    """
    Node 3: Validate extracted features using QualityEvaluator.
    On pass: routes → assign_sprints.
    On fail with retries remaining: sets retry_hint, increments retry_count.
    On fail with no retries left: raises AgentExecutionError.
    """
    retry_count = state.get("retry_count", 0)
    logger.info(
        f"[tracker_agent] validate_features_node retry_count={retry_count} "
        f"features={len(state.get('extracted_features', []))}"
    )

    report = QualityEvaluator().evaluate_s4({"features": state.get("extracted_features", [])})

    if report.passed:
        logger.info("[tracker_agent] Feature validation passed")
        return state

    # Validation failed
    if retry_count >= 2:
        issues_str = "; ".join(report.issues)
        logger.error(
            f"[tracker_agent] Validation failed after {retry_count} retries: {issues_str}"
        )
        raise AgentExecutionError(
            f"Feature decomposition failed after {retry_count} retries. Issues: {issues_str}"
        )

    logger.warning(
        f"[tracker_agent] Validation failed (retry {retry_count + 1}/2): {report.retry_hint}"
    )
    return {
        **state,
        "retry_hint": report.retry_hint,
        "retry_count": retry_count + 1,
    }


def route_validate_features(state: TrackerState) -> str:
    """Route after validate_features_node: assign_sprints if valid, retry decompose if not."""
    # If retry_hint was just set (meaning validation failed), route back to decompose
    # We detect this by checking if retry_count was incremented vs extracted_features validity
    report = QualityEvaluator().evaluate_s4({"features": state.get("extracted_features", [])})
    if report.passed:
        return "assign_sprints"
    # retry_count already incremented in validate_features_node before reaching here
    return "retry"


def assign_sprints_node(state: TrackerState) -> TrackerState:
    """
    Node 4: Deterministic bin-packing of features into sprints.
    """
    logger.info(
        f"[tracker_agent] Assigning {len(state['extracted_features'])} features "
        f"to {state['sprint_count']} sprints"
    )

    try:
        # Convert extracted features to Feature objects
        features = []
        for feat_dict in state["extracted_features"]:
            feature = Feature(
                name=feat_dict["name"],
                description=feat_dict["description"],
                size=feat_dict["size"],
                dependencies=feat_dict.get("dependencies", []),
            )
            features.append(feature)

        # Assign to sprints
        assignment = assign_sprints(
            features=features,
            sprint_count=state["sprint_count"],
            sprint_capacity=state["sprint_capacity"],
        )

        state["sprint_assignment"] = {
            "sprint_plans": [
                {"feature": sp.feature.model_dump(), "sprint_number": sp.sprint_number}
                for sp in assignment.sprint_plans
            ],
            "sprint_summaries": assignment.sprint_summaries,
            "total_points": assignment.total_points,
            "warnings": assignment.warnings,
        }

        logger.info(
            f"[tracker_agent] Sprint assignment complete. "
            f"Total points: {assignment.total_points}, Warnings: {len(assignment.warnings)}"
        )

    except Exception as e:
        error_msg = f"Sprint assignment failed: {e}"
        logger.error(f"[tracker_agent] {error_msg}")
        state["error"] = error_msg
        raise AgentExecutionError(error_msg)

    return state


def build_tracker_graph():
    """Build and compile the tracker agent StateGraph."""
    workflow = StateGraph(TrackerState)

    # Add nodes
    workflow.add_node("read_documents", read_documents_node)
    workflow.add_node("decompose_features", decompose_features_node)
    workflow.add_node("validate_features", validate_features_node)
    workflow.add_node("assign_sprints", assign_sprints_node)

    # Define edges
    workflow.set_entry_point("read_documents")
    workflow.add_edge("read_documents", "decompose_features")
    workflow.add_edge("decompose_features", "validate_features")
    workflow.add_conditional_edges(
        "validate_features",
        route_validate_features,
        {
            "assign_sprints": "assign_sprints",
            "retry": "decompose_features",
        },
    )
    workflow.add_edge("assign_sprints", END)

    return workflow.compile()


# Keep backward-compat alias
create_tracker_graph = build_tracker_graph


async def run_tracker_agent(
    use_case_id: str,
    process_name: str,
    process_description: str,
    complexity_class: str,
    effort_weeks: int,
    sprint_count: int,
    sprint_capacity: int = 8,
) -> dict:
    """
    Run the tracker agent to decompose features and assign sprints.

    Returns:
        dict with extracted_features, sprint_assignment, and metadata
    """
    logger.info(f"[tracker_agent] Starting for use case {use_case_id}")

    initial_state: TrackerState = {
        "use_case_id": use_case_id,
        "process_name": process_name,
        "process_description": process_description,
        "complexity_class": complexity_class,
        "effort_weeks": effort_weeks,
        "sprint_count": sprint_count,
        "sprint_capacity": sprint_capacity,
        "document_context": "",
        "raw_llm_response": "",
        "extracted_features": [],
        "sprint_assignment": {},
        "error": None,
        "retry_count": 0,
        "retry_hint": None,
    }

    graph = build_tracker_graph()

    try:
        final_state = await graph.ainvoke(initial_state)

        if final_state.get("error"):
            raise AgentExecutionError(final_state["error"])

        result = {
            "features": final_state["extracted_features"],
            "sprint_assignment": final_state["sprint_assignment"],
            "raw_llm_response": final_state["raw_llm_response"],
            "metadata": {
                "complexity_class": complexity_class,
                "effort_weeks": effort_weeks,
                "sprint_count": sprint_count,
                "sprint_capacity": sprint_capacity,
                "total_features": len(final_state["extracted_features"]),
                "total_points": final_state["sprint_assignment"]["total_points"],
                "retry_count": final_state.get("retry_count", 0),
            },
        }

        logger.info(f"[tracker_agent] Completed successfully for use case {use_case_id}")
        return result

    except Exception as e:
        logger.error(f"[tracker_agent] Failed: {e}")
        raise AgentExecutionError(f"Tracker agent failed: {e}")
