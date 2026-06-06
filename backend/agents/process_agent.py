"""
Process agent — extracts complexity bands from document text using LLM.
Uses Haiku via LLMManager.
LangGraph StateGraph: extract_bands → validate_bands → END (with retry loop up to 2 retries).
"""

import json
import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from core.exceptions import AgentExecutionError, LLMProviderError
from core.models.scoring import AttributeBandsWithSource
from core.quality import QualityEvaluator
from llm.manager import get_default_manager
from prompts.complexity_prompts import ACTIVE_S2_EXTRACTION_SYSTEM, ACTIVE_S2_EXTRACTION_USER

logger = logging.getLogger(__name__)


class ProcessState(TypedDict):
    """State for process extraction with retry and reflexion support."""

    document_text: str
    model: str
    bands: dict | None  # raw extracted bands dict
    process_summary: dict | None  # NEW: process summary with justification arrays
    extraction_notes: str  # from LLM
    retry_count: int
    retry_hint: str | None  # from QualityEvaluator on failure
    reflexion_count: int  # NEW: count of reflexion attempts
    reflexion_errors: list[str]  # NEW: validation errors triggering reflexion
    error: str | None
    result: AttributeBandsWithSource | None


def parse_llm_json(response: str) -> dict:
    """
    Parse LLM response as JSON, handling common formatting issues.
    Strips markdown fences and preamble/postamble.

    Args:
        response: Raw LLM response text

    Returns:
        Parsed JSON dict

    Raises:
        AgentExecutionError: If JSON cannot be parsed
    """
    text = response.strip()

    # Strip markdown fences
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise AgentExecutionError(f"No JSON object found in LLM response: {response[:200]}")

    json_text = text[start : end + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise AgentExecutionError(f"Failed to parse LLM JSON: {e}. Text: {json_text[:200]}")


async def extract_bands_node(state: ProcessState) -> ProcessState:
    """
    Node 1: Call LLM to extract complexity bands.
    When retry_hint is set, appends correction hint to the user prompt.
    """
    retry_count = state.get("retry_count", 0)
    logger.info(
        f"[process_agent] extract_bands_node attempt={retry_count + 1} "
        f"chars={len(state['document_text'])} model={state['model']}"
    )

    llm = get_default_manager()
    system_prompt = ACTIVE_S2_EXTRACTION_SYSTEM
    user_prompt = ACTIVE_S2_EXTRACTION_USER.format(document_text=state["document_text"])

    if state.get("retry_hint"):
        user_prompt += (
            f"\n\nPrevious attempt was invalid: {state['retry_hint']}. Please fix and retry."
        )
        logger.info(f"[process_agent] Retrying with hint: {state['retry_hint']}")

    try:
        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=800,
            temperature=0.2,
        )
    except Exception as e:
        raise LLMProviderError(f"LLM call failed: {e}")

    try:
        data = parse_llm_json(response)
    except AgentExecutionError:
        raise

    extraction_notes = data.get("extraction_notes", "")
    process_summary = data.get("process_summary", {})
    logger.info(f"[process_agent] Raw bands parsed. Notes: {extraction_notes}")
    if process_summary:
        logger.info(
            f"[process_agent] process_summary present with {len(process_summary.get('key_activities', []))} activities"
        )

    return {
        **state,
        "bands": data,
        "process_summary": process_summary,
        "extraction_notes": extraction_notes,
    }


def validate_bands_node(state: ProcessState) -> ProcessState:
    """
    Node 2: Validate extracted bands using QualityEvaluator.
    On pass: builds AttributeBandsWithSource and sets state['result'].
    On fail with retries remaining: sets retry_hint, increments retry_count.
    On fail with no retries left: raises AgentExecutionError.
    """
    logger.info(
        f"[process_agent] validate_bands_node retry_count={state.get('retry_count', 0)}"
    )

    report = QualityEvaluator().evaluate_s2(state.get("bands") or {})

    if report.passed:
        data = state["bands"]
        try:
            bands = AttributeBandsWithSource(
                activities=data["activities"],
                activities_source="ai_extracted",
                business_rules=data["business_rules"],
                business_rules_source="ai_extracted",
                layouts=data["layouts"],
                layouts_source="ai_extracted",
                interfaces=data["interfaces"],
                interfaces_source="ai_extracted",
                technology=data["technology"],
                technology_source="ai_extracted",
            )
        except (KeyError, ValidationError) as e:
            raise AgentExecutionError(f"Invalid band data from LLM: {e}. Data: {data}")

        logger.info(f"[process_agent] Validation passed. Bands: {bands.model_dump()}")
        return {**state, "result": bands}

    # Validation failed
    retry_count = state.get("retry_count", 0)
    if retry_count >= 2:
        issues_str = "; ".join(report.issues)
        logger.error(
            f"[process_agent] Validation failed after {retry_count} retries: {issues_str}"
        )
        raise AgentExecutionError(
            f"Band extraction failed after {retry_count} retries. Issues: {issues_str}"
        )

    logger.warning(
        f"[process_agent] Validation failed (retry {retry_count + 1}/2): {report.retry_hint}"
    )
    return {
        **state,
        "retry_hint": report.retry_hint,
        "retry_count": retry_count + 1,
    }


def route_validate(state: ProcessState) -> str:
    """Route after validate_bands_node: end if result set, retry if hint set, else reflexion check."""
    if state.get("result") is not None:
        # Passed basic validation, proceed to reflexion validation
        return "reflexion"
    if state.get("retry_count", 0) <= 2 and state.get("retry_hint"):
        return "retry"
    return "end"


def validate_justification_node(state: ProcessState) -> ProcessState:
    """
    Node 3 (NEW): Reflexion validation - ensure process_summary arrays justify bands.

    Checks that array counts align with band classifications.
    If misaligned and reflexion_count < 2: trigger reflexion correction.
    If aligned or exhausted retries: pass through.
    """
    from prompts.reflexion_validation_prompts import BAND_RANGES

    logger.info(
        f"[process_agent] validate_justification_node reflexion_count={state.get('reflexion_count', 0)}"
    )

    process_summary = state.get("process_summary")
    if not process_summary:
        logger.warning("[process_agent] No process_summary found, skipping reflexion validation")
        return state

    bands = state["bands"]
    errors = []

    # Band to array mapping
    checks = [
        ("activities", "key_activities"),
        ("business_rules", "key_logical_points"),
        ("layouts", "key_layouts"),
        ("interfaces", "key_applications"),
        ("technology", "key_additional_technologies"),
    ]

    for band_key, array_key in checks:
        band_value = bands.get(band_key)
        array_items = process_summary.get(array_key, [])
        array_count = len(array_items)

        # Get expected range
        expected_range = BAND_RANGES.get(band_key, {}).get(band_value, "unknown")

        # Validate count alignment (approximate check)
        is_valid = _check_count_alignment(band_value, array_count, band_key)

        if not is_valid:
            errors.append(
                f"{band_key}={band_value} expects {expected_range} items "
                f"but got {array_count} in {array_key}"
            )

    if errors:
        reflexion_count = state.get("reflexion_count", 0)
        if reflexion_count >= 2:
            logger.warning(
                f"[process_agent] Justification validation failed after {reflexion_count} "
                f"reflexion attempts. Proceeding anyway. Errors: {errors}"
            )
            return state
        else:
            logger.warning(
                f"[process_agent] Justification misalignment detected (attempt {reflexion_count + 1}/2): {errors}"
            )
            return {
                **state,
                "reflexion_errors": errors,
                "reflexion_count": reflexion_count + 1,
            }

    logger.info("[process_agent] Justification validation passed")
    return state


def _check_count_alignment(band: str, count: int, attribute: str) -> bool:
    """Check if array count aligns with band classification (approximate)."""
    if attribute == "activities":
        ranges = {"XS": (1, 5), "S": (6, 10), "M": (11, 20), "L": (21, 40), "XL": (41, 100)}
    elif attribute == "business_rules":
        ranges = {"XS": (0, 0), "S": (1, 2), "M": (3, 4), "L": (4, 5), "XL": (5, 10)}
    elif attribute == "layouts":
        ranges = {"XS": (1, 1), "S": (2, 2), "M": (3, 3), "L": (4, 6), "XL": (7, 20)}
    elif attribute == "interfaces":
        ranges = {"XS": (0, 0), "S": (1, 2), "M": (3, 3), "L": (4, 4), "XL": (5, 10)}
    elif attribute == "technology":
        ranges = {"XS": (0, 0), "S": (1, 2), "M": (3, 4), "L": (5, 6), "XL": (7, 20)}
    else:
        return True  # Unknown attribute, pass

    min_count, max_count = ranges.get(band, (0, 100))
    return min_count <= count <= max_count


async def reflexion_correct_node(state: ProcessState) -> ProcessState:
    """
    Node 4 (NEW): Invoke LLM with reflexion prompt to self-correct misaligned extraction.
    """
    from prompts.reflexion_validation_prompts import (
        BAND_RANGES,
        REFLEXION_S2_JUSTIFICATION_SYSTEM,
        REFLEXION_S2_JUSTIFICATION_USER,
    )

    logger.info(
        f"[process_agent] reflexion_correct_node attempt={state['reflexion_count']} "
        f"errors={len(state.get('reflexion_errors', []))}"
    )

    bands = state["bands"]
    process_summary = state["process_summary"]

    # Build validation error details
    validation_errors = "\n".join(
        f"- {error}" for error in state.get("reflexion_errors", [])
    )

    # Build expected ranges for each band
    band_details = {}
    for band_key, array_key in [
        ("activities", "key_activities"),
        ("business_rules", "key_logical_points"),
        ("layouts", "key_layouts"),
        ("interfaces", "key_applications"),
        ("technology", "key_additional_technologies"),
    ]:
        band_value = bands.get(band_key)
        array_count = len(process_summary.get(array_key, []))
        expected_range = BAND_RANGES.get(band_key, {}).get(band_value, "unknown")

        band_details[f"{band_key}_band"] = band_value
        band_details[f"{band_key}_range"] = expected_range
        band_details[f"{band_key}_count"] = array_count

    system_prompt = REFLEXION_S2_JUSTIFICATION_SYSTEM.format(
        validation_errors=validation_errors,
        **band_details,
    )

    user_prompt = REFLEXION_S2_JUSTIFICATION_USER.format(
        original_extraction=json.dumps(
            {"bands": bands, "process_summary": process_summary}, indent=2
        )
    )

    llm = get_default_manager()

    try:
        response = await llm.complete_async(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=1200,
            temperature=0.2,
        )
    except Exception as e:
        logger.error(f"[process_agent] Reflexion LLM call failed: {e}")
        # Fall back to original extraction
        return state

    try:
        corrected_data = parse_llm_json(response)
        logger.info(
            f"[process_agent] Reflexion correction applied. "
            f"New activities band: {corrected_data.get('activities')}"
        )

        return {
            **state,
            "bands": corrected_data,
            "process_summary": corrected_data.get("process_summary", {}),
            "reflexion_errors": [],  # Clear errors after correction
        }
    except AgentExecutionError as e:
        logger.error(f"[process_agent] Failed to parse reflexion correction: {e}")
        return state


def route_reflexion(state: ProcessState) -> str:
    """Route after reflexion validation: correct if errors, otherwise end."""
    if state.get("reflexion_errors") and state.get("reflexion_count", 0) < 2:
        return "correct"
    return "end"


def _build_process_graph():
    """Build and compile the process agent LangGraph StateGraph with reflexion validation."""
    workflow = StateGraph(ProcessState)

    workflow.add_node("extract_bands", extract_bands_node)
    workflow.add_node("validate_bands", validate_bands_node)
    workflow.add_node("validate_justification", validate_justification_node)
    workflow.add_node("reflexion_correct", reflexion_correct_node)

    workflow.set_entry_point("extract_bands")
    workflow.add_edge("extract_bands", "validate_bands")
    workflow.add_conditional_edges(
        "validate_bands",
        route_validate,
        {
            "end": END,
            "retry": "extract_bands",
            "reflexion": "validate_justification",
        },
    )
    workflow.add_conditional_edges(
        "validate_justification",
        route_reflexion,
        {
            "end": END,
            "correct": "reflexion_correct",
        },
    )
    # After correction, loop back to validate_justification to check again
    workflow.add_edge("reflexion_correct", "validate_justification")

    return workflow.compile()


async def extract_bands_from_text(
    document_text: str, model: str = "claude-haiku-4-5"
) -> AttributeBandsWithSource:
    """
    Extract complexity bands from document text using LLM.
    Public entry point — builds LangGraph, invokes async, returns result.

    Args:
        document_text: Raw text from document
        model: LLM model to use (default: claude-haiku-4-5)

    Returns:
        AttributeBandsWithSource with all sources set to 'ai_extracted'

    Raises:
        LLMProviderError: If LLM call fails
        AgentExecutionError: If response cannot be parsed or validation fails after retries
    """
    logger.info(
        f"[process_agent] Starting extraction: {len(document_text)} chars, model={model}"
    )

    graph = _build_process_graph()
    initial_state: ProcessState = {
        "document_text": document_text,
        "model": model,
        "bands": None,
        "process_summary": None,
        "extraction_notes": "",
        "retry_count": 0,
        "retry_hint": None,
        "reflexion_count": 0,
        "reflexion_errors": [],
        "error": None,
        "result": None,
    }

    final_state = await graph.ainvoke(initial_state)

    if final_state.get("result") is None:
        raise AgentExecutionError(
            f"Band extraction failed: {final_state.get('error', 'unknown error')}"
        )

    logger.info("[process_agent] Extraction complete")
    result = final_state["result"]

    # Attach process_summary to result for downstream use (stored as attribute)
    process_summary = final_state.get("process_summary")
    if process_summary:
        # Store as dict attribute on Pydantic model
        result.__dict__["_process_summary"] = process_summary

    return result
