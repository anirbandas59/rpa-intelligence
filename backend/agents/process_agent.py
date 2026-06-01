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
    """State for process extraction with retry support."""

    document_text: str
    model: str
    bands: dict | None  # raw extracted bands dict
    extraction_notes: str  # from LLM
    retry_count: int
    retry_hint: str | None  # from QualityEvaluator on failure
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
    logger.info(f"[process_agent] Raw bands parsed. Notes: {extraction_notes}")

    return {
        **state,
        "bands": data,
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
    """Route after validate_bands_node: end if result set, retry if hint set, else end."""
    if state.get("result") is not None:
        return "end"
    if state.get("retry_count", 0) <= 2 and state.get("retry_hint"):
        return "retry"
    return "end"


def _build_process_graph():
    """Build and compile the process agent LangGraph StateGraph."""
    workflow = StateGraph(ProcessState)

    workflow.add_node("extract_bands", extract_bands_node)
    workflow.add_node("validate_bands", validate_bands_node)

    workflow.set_entry_point("extract_bands")
    workflow.add_edge("extract_bands", "validate_bands")
    workflow.add_conditional_edges(
        "validate_bands",
        route_validate,
        {
            "end": END,
            "retry": "extract_bands",
        },
    )

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
        "extraction_notes": "",
        "retry_count": 0,
        "retry_hint": None,
        "error": None,
        "result": None,
    }

    final_state = await graph.ainvoke(initial_state)

    if final_state.get("result") is None:
        raise AgentExecutionError(
            f"Band extraction failed: {final_state.get('error', 'unknown error')}"
        )

    return final_state["result"]
