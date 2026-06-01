"""
Process agent — extracts complexity bands from document text using LLM.
Uses Haiku via LLMManager.
Parses JSON response into AttributeBandsWithSource.
"""

import json
import logging
from typing import TypedDict
from pydantic import ValidationError
from llm.manager import LLMManager
from prompts.complexity_prompts import ACTIVE_S2_EXTRACTION_SYSTEM, ACTIVE_S2_EXTRACTION_USER
from core.models.scoring import AttributeBandsWithSource
from core.exceptions import LLMProviderError, AgentExecutionError

logger = logging.getLogger(__name__)


class ProcessState(TypedDict):
    """State for process extraction."""

    document_text: str
    bands: AttributeBandsWithSource | None
    extraction_notes: str | None
    error: str | None


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


def extract_bands_from_text(document_text: str, model: str = "claude-haiku-4-5") -> AttributeBandsWithSource:
    """
    Extract complexity bands from document text using LLM.
    Entry point for process agent.

    Args:
        document_text: Raw text from document
        model: LLM model to use (default: claude-haiku-4-5)

    Returns:
        AttributeBandsWithSource with all sources set to 'ai_extracted'

    Raises:
        LLMProviderError: If LLM call fails
        AgentExecutionError: If response cannot be parsed
    """
    logger.info(f"Extracting bands from {len(document_text)} chars using {model}")

    llm = LLMManager()
    system_prompt = ACTIVE_S2_EXTRACTION_SYSTEM
    user_prompt = ACTIVE_S2_EXTRACTION_USER.format(document_text=document_text)

    try:
        response = llm.complete(
            system=system_prompt,
            prompt=user_prompt,
            max_tokens=800,
            temperature=0.2,
        )
    except Exception as e:
        raise LLMProviderError(f"LLM call failed: {e}")

    # Parse JSON response
    try:
        data = parse_llm_json(response)
    except AgentExecutionError:
        raise

    # Validate and construct AttributeBandsWithSource
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

    extraction_notes = data.get("extraction_notes", "")
    logger.info(f"Extracted bands: {bands.model_dump()}. Notes: {extraction_notes}")

    return bands
