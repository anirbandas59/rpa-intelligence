"""
Task Extraction Agent with Tools (Stage 3 Job A - Tool-Based Approach)

Similar to process_agent_with_tools.py for S2, this agent uses LangGraph with tools
to allow the LLM to validate hour sums during reasoning, improving accuracy.

Architecture:
- LLM can call validate_hour_sum_tool() during extraction
- LLM can call calculate_average_hours_tool() to help distribute hours
- Tool results ground the LLM's reasoning
- Reduces hallucination compared to prompt-only approach
"""

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from core.exceptions import AgentExecutionError
from llm.manager import get_stage_manager
from prompts.task_extraction_prompts import TASK_EXTRACTION_SYSTEM, TASK_EXTRACTION_USER
from tools.analysis.task_extraction_tool import TaskExtractionResult, parse_task_extraction

logger = logging.getLogger(__name__)


# ===== TOOLS =====


@tool
def calculate_average_hours(total_budget: float, num_steps: int) -> dict:
    """
    Calculate average hours per step given total budget and number of steps.

    Args:
        total_budget: Total effort hours available
        num_steps: Number of development steps (where reusability != "full")

    Returns:
        Dictionary with average_hours and suggestions for adjustment
    """
    if num_steps == 0:
        return {
            "average_hours": 0.0,
            "error": "Cannot calculate average with 0 steps"
        }

    avg = total_budget / num_steps

    return {
        "average_hours": round(avg, 2),
        "total_budget": total_budget,
        "num_steps": num_steps,
        "suggestion": f"Assign approximately {avg:.1f}h per step, then adjust based on complexity. Simple steps: {avg*0.5:.1f}h, Complex steps: {avg*1.5:.1f}h"
    }


@tool
def validate_task_hour_sum(
    steps_json: str,
    total_budget: float,
    tolerance: float = 0.5
) -> dict:
    """
    Validate that step hours sum to total budget.

    Args:
        steps_json: JSON string array of steps with weight_hours and reusability
        total_budget: Expected total hours
        tolerance: Acceptable difference (default 0.5h)

    Returns:
        Dictionary with validation result, actual_sum, and guidance

    Example:
        steps_json = '[{"weight_hours": 20.0, "reusability": "none"}, {"weight_hours": 15.0, "reusability": "partial"}]'
        validate_task_hour_sum(steps_json, 35.0) → {"valid": True, "actual_sum": 35.0, ...}
    """
    try:
        steps = json.loads(steps_json)

        # Calculate sum of non-full-reuse steps
        actual_sum = 0.0
        for step in steps:
            if step.get("reusability") != "full":
                actual_sum += step.get("weight_hours", 0.0)

        diff = abs(actual_sum - total_budget)
        valid = diff <= tolerance

        result = {
            "valid": valid,
            "actual_sum": round(actual_sum, 2),
            "expected": round(total_budget, 2),
            "difference": round(diff, 2),
            "tolerance": tolerance,
            "num_steps": len([s for s in steps if s.get("reusability") != "full"]),
        }

        if valid:
            result["message"] = f"✓ Hour sum valid: {actual_sum:.2f}h matches budget {total_budget:.2f}h (diff: {diff:.2f}h)"
        else:
            result["message"] = f"✗ Hour sum invalid: {actual_sum:.2f}h != {total_budget:.2f}h (diff: {diff:.2f}h, tolerance: {tolerance}h)"
            result["guidance"] = f"Adjust step hours. Current sum is {'over' if actual_sum > total_budget else 'under'} budget by {diff:.2f}h"

        return result

    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "error": f"Invalid JSON: {str(e)}"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Validation error: {str(e)}"
        }


# ===== STATE =====


class TaskExtractionState(BaseModel):
    """State for task extraction agent."""

    session_id: str
    document_text: str
    process_name: str
    total_effort_hours: float
    process_summary: dict | None = None

    messages: list = Field(default_factory=list)
    result: TaskExtractionResult | None = None
    error: str | None = None
    attempts: int = 0


# ===== NODES =====


def call_llm_node(state: TaskExtractionState) -> dict:
    """
    Node that calls LLM with tools available.

    LLM can use:
    - calculate_average_hours(total_budget, num_steps) to plan distribution
    - validate_task_hour_sum(steps_json, total_budget) to check sum
    """
    session_id = state.session_id
    logger.info("call_llm_node entered", extra={"session_id": session_id})

    # Get stage-specific LLM
    llm = get_stage_manager("s3_task_extraction")

    # Bind tools to LLM
    llm_with_tools = llm.client.bind_tools([calculate_average_hours, validate_task_hour_sum])

    # Invoke LLM
    response = llm_with_tools.invoke(state.messages)

    logger.info(
        f"LLM responded with {len(response.tool_calls) if hasattr(response, 'tool_calls') else 0} tool calls",
        extra={"session_id": session_id}
    )

    return {"messages": state.messages + [response], "attempts": state.attempts + 1}


def should_continue(state: TaskExtractionState) -> str:
    """Decide whether to call tools, extract result, or end."""
    last_message = state.messages[-1]

    # If LLM called tools, execute them
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # If no tools called, try to extract result
    return "extract"


def extract_result_node(state: TaskExtractionState) -> dict:
    """Parse LLM response and validate hour sum."""
    session_id = state.session_id
    logger.info("extract_result_node entered", extra={"session_id": session_id})

    last_message = state.messages[-1]

    try:
        # Get LLM's response content
        if isinstance(last_message, AIMessage):
            raw_response = last_message.content
        else:
            raw_response = str(last_message)

        # Parse to Pydantic model
        result = parse_task_extraction(raw_response)

        # Validate hour sum
        actual_sum = sum(
            step.weight_hours
            for activity in result.activities
            for step in activity.steps
            if step.reusability != "full"
        )

        diff = abs(actual_sum - state.total_effort_hours)

        if diff <= 0.5:
            logger.info(
                f"Hour sum valid: {actual_sum:.2f}h ≈ {state.total_effort_hours:.2f}h",
                extra={"session_id": session_id}
            )
            return {"result": result, "error": None}
        else:
            # Validation failed
            if state.attempts >= 3:
                error_msg = (
                    f"Hour sum validation failed after {state.attempts} attempts. "
                    f"Expected {state.total_effort_hours:.2f}h but got {actual_sum:.2f}h (step-level sum). "
                    f"LLM reported total_net_hours: {result.total_net_hours:.2f}h"
                )
                logger.error(error_msg, extra={"session_id": session_id})
                return {"error": error_msg}
            else:
                # Retry with feedback
                retry_message = HumanMessage(
                    content=(
                        f"Hour sum validation FAILED. "
                        f"Step-level sum is {actual_sum:.2f}h but must equal {state.total_effort_hours:.2f}h exactly. "
                        f"Difference: {diff:.2f}h. "
                        f"Use the validate_task_hour_sum tool to check your work BEFORE returning JSON. "
                        f"Rebalance step weights and try again."
                    )
                )
                logger.warning(
                    f"Retrying extraction (attempt {state.attempts}/3)",
                    extra={"session_id": session_id}
                )
                return {"messages": state.messages + [retry_message]}

    except Exception as e:
        error_msg = f"Failed to parse task extraction: {str(e)}"
        logger.error(error_msg, extra={"session_id": session_id})
        return {"error": error_msg}


# ===== GRAPH =====


def create_task_extraction_graph():
    """Create LangGraph StateGraph for task extraction with tools."""
    workflow = StateGraph(TaskExtractionState)

    # Add nodes
    workflow.add_node("call_llm", call_llm_node)
    workflow.add_node("tools", ToolNode([calculate_average_hours, validate_task_hour_sum]))
    workflow.add_node("extract", extract_result_node)

    # Set entry point
    workflow.set_entry_point("call_llm")

    # Add edges
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "tools": "tools",
            "extract": "extract",
        }
    )

    # Tools return to LLM
    workflow.add_edge("tools", "call_llm")

    # Extract either ends or retries
    workflow.add_conditional_edges(
        "extract",
        lambda s: "end" if (s.result is not None or s.error is not None or s.attempts >= 3) else "call_llm",
        {
            "end": END,
            "call_llm": "call_llm",
        }
    )

    return workflow.compile()


# ===== PUBLIC API =====


async def extract_tasks_with_tools(
    document_text: str,
    process_name: str,
    total_effort_hours: float,
    process_summary: dict | None = None,
    session_id: str = "default",
) -> tuple[TaskExtractionResult | None, str | None]:
    """
    Extract task breakdown using tool-based agent.

    Args:
        document_text: Process document (PDD/SDD) text
        process_name: Name of process
        total_effort_hours: Total effort budget in hours
        process_summary: Optional S2 process summary for context
        session_id: Session ID for logging

    Returns:
        Tuple of (TaskExtractionResult or None, error message or None)

    Raises:
        AgentExecutionError: If extraction fails after max attempts
    """
    logger.info(
        f"Starting tool-based task extraction for {process_name} ({total_effort_hours}h)",
        extra={"session_id": session_id}
    )

    # Build context from S2 process summary
    process_context = ""
    if process_summary:
        process_context = f"""
Stage 2 Process Understanding:
- Key Activities: {', '.join(process_summary.get('key_activities', []))}
- Business Rules: {', '.join(process_summary.get('key_logical_points', []))}
- Applications: {', '.join(process_summary.get('key_applications', []))}
- Technologies: {', '.join(process_summary.get('key_additional_technologies', []))}
"""

    # Format prompts
    system_prompt = TASK_EXTRACTION_SYSTEM.format(total_effort_hours=total_effort_hours)
    user_prompt = TASK_EXTRACTION_USER.format(
        document_text=document_text,
        process_context=process_context,
        total_effort_hours=total_effort_hours,
        process_name=process_name
    )

    # Initial state
    initial_state = TaskExtractionState(
        session_id=session_id,
        document_text=document_text,
        process_name=process_name,
        total_effort_hours=total_effort_hours,
        process_summary=process_summary,
        messages=[
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ],
        attempts=0
    )

    # Run graph
    graph = create_task_extraction_graph()

    try:
        final_state = await graph.ainvoke(initial_state)

        if final_state.result:
            logger.info(
                f"Task extraction succeeded with {len(final_state.result.activities)} activities",
                extra={"session_id": session_id}
            )
            return (final_state.result, None)
        elif final_state.error:
            logger.error(
                f"Task extraction failed: {final_state.error}",
                extra={"session_id": session_id}
            )
            return (None, final_state.error)
        else:
            error_msg = "Task extraction failed with no result or error"
            logger.error(error_msg, extra={"session_id": session_id})
            return (None, error_msg)

    except Exception as e:
        error_msg = f"Task extraction agent error: {str(e)}"
        logger.exception(error_msg, extra={"session_id": session_id})
        raise AgentExecutionError(error_msg) from e
