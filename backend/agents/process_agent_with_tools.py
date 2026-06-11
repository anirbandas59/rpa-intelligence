"""
Process agent with tool binding — extracts complexity bands using LLM + validation tools.

This is an enhanced version of process_agent.py that uses LangChain's tool binding
to give the LLM access to the weight matrix validation functions. Instead of
guessing band values, the LLM can:

1. Count items in the document (e.g., "I found 3 business rules")
2. Call get_band_for_count("business_rules", 3) to verify the correct band
3. Self-validate before returning the final answer

This reduces hallucination and improves accuracy by grounding band assignments
in the actual weight matrix logic.

Workflow: extract_with_tools → validate_structure → END
(No retry loop needed - LLM self-corrects using tools)
"""

import json
import logging
from typing import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from config.settings import get_settings
from core.exceptions import AgentExecutionError
from core.models.scoring import AttributeBandsWithSource
from tools.analysis.attribute_validation_tool import (
    get_attribute_definitions,
    get_band_for_count,
    get_band_ranges,
)

logger = logging.getLogger("rpa_agent.process_agent_with_tools")


# Define tools for LLM access
@tool
def validate_band_for_count(attribute_name: str, count: int) -> str:
    """
    Given an attribute name and the count of items found in the document,
    return the correct complexity band according to the weight matrix.

    Use this tool to verify your band assignments are correct.

    Args:
        attribute_name: One of "activities", "business_rules", "layouts",
                       "interfaces", or "technology"
        count: The number of items you counted in the document

    Returns:
        The correct band: "S", "M", "L", or "XL"

    Examples:
        - validate_band_for_count("business_rules", 3) → "L"
        - validate_band_for_count("activities", 15) → "M"
    """
    return get_band_for_count(attribute_name, count)


@tool
def get_attribute_descriptions() -> dict:
    """
    Get detailed descriptions of what each attribute represents.

    Use this to understand the difference between similar attributes
    (e.g., layouts vs interfaces).

    Returns:
        Dictionary mapping attribute names to their descriptions
    """
    return get_attribute_definitions()


@tool
def get_band_thresholds() -> dict:
    """
    Get the count ranges that determine each band for all attributes.

    Use this to understand how many items correspond to each band.

    Returns:
        Nested dict: {attribute: {band: range_description}}

    Example output:
        {
            "business_rules": {
                "S": "0 rules",
                "M": "1-2 rules",
                "L": "3-4 rules",
                "XL": "5+ rules"
            },
            ...
        }
    """
    return get_band_ranges()


# Tool list for binding
EXTRACTION_TOOLS = [
    validate_band_for_count,
    get_attribute_descriptions,
    get_band_thresholds,
]


class ProcessStateWithTools(TypedDict):
    """State for tool-based process extraction."""

    document_text: str
    model: str
    messages: list  # LangChain message history
    bands: dict | None  # Final extracted bands
    process_summary: dict | None
    extraction_notes: str
    error: str | None
    result: AttributeBandsWithSource | None


SYSTEM_PROMPT = """You are an RPA process analyst with access to validation tools.

Your task: Extract complexity attribute bands from a process document.

## Available Attributes

1. **activities**: Number of distinct automation steps/actions
2. **business_rules**: Number of conditional logic branches or decision rules
3. **layouts**: Number of distinct UI screens or forms
4. **interfaces**: Number of external systems/APIs to integrate with
5. **technology**: Number of additional technology integration points

## Your Workflow

1. **Read the document** and identify each attribute
2. **Count items** for each attribute (e.g., count distinct activities)
3. **Use validate_band_for_count(attribute, count)** to get the correct band
4. **Build process_summary** with specific examples from the document
5. **Return structured JSON** with your findings

## Critical Rules

- ALWAYS use validate_band_for_count() to verify each band assignment
- Count actual items from the document, don't estimate
- process_summary arrays should contain SPECIFIC items from the document
- The count of items in each process_summary array should justify your band choice

## Response Format

Return ONLY valid JSON (no markdown fences):

{
  "activities": "S|M|L|XL",
  "business_rules": "S|M|L|XL",
  "layouts": "S|M|L|XL",
  "interfaces": "S|M|L|XL",
  "technology": "S|M|L|XL",
  "extraction_notes": "Brief notes on your analysis",
  "process_summary": {
    "overall_summary": "1-2 sentence process overview",
    "key_activities": ["specific activity 1", "specific activity 2", ...],
    "key_logical_points": ["specific rule 1", "specific rule 2", ...],
    "key_applications": ["system name 1", "system name 2", ...],
    "key_layouts": ["screen name 1", "screen name 2", ...],
    "key_additional_technologies": ["tech 1", "tech 2", ...]
  }
}

## Example Tool Usage

If you find 3 business rules in the document:
1. List them in process_summary.key_logical_points
2. Call: validate_band_for_count("business_rules", 3)
3. Tool returns: "L"
4. Set: "business_rules": "L"

This ensures your band assignments are grounded in the weight matrix.
"""


async def extract_with_tools_node(state: ProcessStateWithTools) -> dict:
    """
    Node 1: Extract bands using LLM with tool access.

    The LLM can call validation tools to verify its band assignments,
    reducing hallucination and improving accuracy.
    """
    logger.info(
        f"[process_agent_tools] extract_with_tools_node "
        f"doc_length={len(state['document_text'])} model={state['model']}"
    )

    settings = get_settings()

    # Initialize LangChain LLM with tools
    llm = ChatAnthropic(
        model=state["model"],
        anthropic_api_key=settings.anthropic_api_key,
        temperature=0.2,
        max_tokens=2000,
    )

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(EXTRACTION_TOOLS)

    # Build messages
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Extract complexity bands from this document:\n\n{state['document_text']}"
        ),
    ]

    try:
        # Multi-turn conversation: LLM → tool calls → results → final JSON
        max_iterations = 5
        for iteration in range(max_iterations):
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

            # Check if LLM made tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.info(
                    f"[process_agent_tools] Iteration {iteration+1}: LLM made {len(response.tool_calls)} tool calls"
                )

                # Execute all tool calls
                tool_results = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    logger.info(
                        f"[process_agent_tools] Calling tool: {tool_name} with args: {tool_args}"
                    )

                    # Find and execute the tool
                    tool_fn = next((t for t in EXTRACTION_TOOLS if t.name == tool_name), None)
                    if tool_fn:
                        result = tool_fn.invoke(tool_args)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call["id"],
                                "content": json.dumps(result) if isinstance(result, dict) else str(result),
                            }
                        )

                # Add tool results as ToolMessage
                from langchain_core.messages import ToolMessage
                for tool_result in tool_results:
                    messages.append(
                        ToolMessage(
                            content=tool_result["content"],
                            tool_call_id=tool_result["tool_use_id"],
                        )
                    )

                # Continue loop - LLM will see tool results and generate final answer
                continue

            # No tool calls - this is the final response
            logger.info(f"[process_agent_tools] Final response received (no more tool calls)")

            # Extract content
            content = response.content
            if isinstance(content, list):
                # Multi-part response - extract text blocks
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = " ".join(text_parts)

            # Parse JSON response
            data = _parse_json_response(content)

            return {
                "bands": data,
                "process_summary": data.get("process_summary", {}),
                "extraction_notes": data.get("extraction_notes", "Tool-based extraction with validation"),
                "messages": messages,
            }

        # Max iterations reached without final answer
        raise AgentExecutionError(f"Max iterations ({max_iterations}) reached without final JSON response")

    except Exception as e:
        error_msg = f"Tool-based extraction failed: {e}"
        logger.error(f"[process_agent_tools] {error_msg}")
        return {"error": error_msg}


def validate_structure_node(state: ProcessStateWithTools) -> dict:
    """
    Node 2: Validate the structure and build final result.

    With tool-based extraction, we expect high accuracy, so we only
    validate structure (not retry band assignments).
    """
    logger.info("[process_agent_tools] validate_structure_node")

    if state.get("error"):
        return {"error": state["error"]}

    data = state.get("bands")
    if not data:
        return {"error": "No bands extracted"}

    # Build AttributeBandsWithSource model
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
        logger.info(
            f"[process_agent_tools] Extraction complete. Bands: {bands.model_dump()}"
        )
        return {"result": bands}

    except (KeyError, ValidationError) as e:
        error_msg = f"Invalid band structure: {e}. Data: {data}"
        logger.error(f"[process_agent_tools] {error_msg}")
        return {"error": error_msg}


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    text = content.strip()

    # Strip markdown fences
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    # Extract JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise AgentExecutionError(f"No JSON in response: {content[:200]}")

    json_text = text[start : end + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise AgentExecutionError(f"Invalid JSON: {e}. Text: {json_text[:200]}")


def build_process_graph_with_tools() -> StateGraph:
    """Build StateGraph for tool-based extraction."""
    workflow = StateGraph(ProcessStateWithTools)

    workflow.add_node("extract_with_tools", extract_with_tools_node)
    workflow.add_node("validate_structure", validate_structure_node)

    workflow.set_entry_point("extract_with_tools")
    workflow.add_edge("extract_with_tools", "validate_structure")
    workflow.add_edge("validate_structure", END)

    return workflow.compile()


async def extract_bands_with_tools(
    document_text: str,
    model: str = "claude-haiku-4-5",
) -> tuple[AttributeBandsWithSource, dict, str]:
    """
    Extract complexity bands using tool-based agent.

    This is a drop-in replacement for the original extract_bands_from_text()
    but uses tool binding for more accurate, grounded extraction.

    Args:
        document_text: Process document text (PDD/SDD)
        model: LLM model to use (default: claude-haiku-4-5)

    Returns:
        Tuple of (bands, process_summary, extraction_notes)

    Raises:
        AgentExecutionError: If extraction fails
        LLMProviderError: If LLM call fails
    """
    logger.info(
        f"[process_agent_tools] Starting tool-based extraction with model={model}"
    )

    initial_state: ProcessStateWithTools = {
        "document_text": document_text,
        "model": model,
        "messages": [],
        "bands": None,
        "process_summary": None,
        "extraction_notes": "",
        "error": None,
        "result": None,
    }

    graph = build_process_graph_with_tools()

    try:
        final_state = await graph.ainvoke(initial_state)

        if final_state.get("error"):
            raise AgentExecutionError(final_state["error"])

        if not final_state.get("result"):
            raise AgentExecutionError("Extraction completed but no result generated")

        return (
            final_state["result"],
            final_state.get("process_summary", {}),
            final_state.get("extraction_notes", ""),
        )

    except Exception as e:
        logger.error(f"[process_agent_tools] Extraction failed: {e}")
        raise AgentExecutionError(f"Tool-based extraction failed: {e}")
