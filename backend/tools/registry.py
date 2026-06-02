"""
Tool Registry — Central registration and discovery for all agentic tools.

Every capability that the orchestrator can invoke is registered here as a ToolDefinition.
Agents use ToolRegistry.get(name) to obtain a tool and call tool.execute(**inputs).

Rules (non-negotiable):
- All tool inputs/outputs are Pydantic models — no raw dicts
- Every registered tool must have a description (used in LLM system prompts)
- execute() is always async
- Fail loudly with ToolNotFoundError if a tool is not registered
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from core.exceptions import RPABaseError

logger = logging.getLogger(__name__)


class ToolNotFoundError(RPABaseError):
    """Raised when a requested tool is not registered."""


class ToolDefinition(BaseModel):
    """Describes a single agentic tool — its identity, schema, and callable."""

    name: str
    description: str  # used verbatim in orchestrator system prompts
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    # execute is not stored as Pydantic field — stored separately

    model_config = {"arbitrary_types_allowed": True}


class RegisteredTool:
    """Wraps a ToolDefinition with its async execute callable."""

    def __init__(
        self,
        definition: ToolDefinition,
        execute_fn: Callable[..., Awaitable[Any]],
    ):
        self.definition = definition
        self._execute_fn = execute_fn

    async def execute(self, **kwargs) -> Any:
        return await self._execute_fn(**kwargs)

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description


class ToolRegistry:
    """Singleton registry for all agentic tools.

    Usage:
        ToolRegistry.register(definition, execute_fn)
        tool = ToolRegistry.get("run_s1_assessment")
        result = await tool.execute(use_case_id="...", db=session)
    """

    _tools: dict[str, RegisteredTool] = {}

    @classmethod
    def register(
        cls,
        definition: ToolDefinition,
        execute_fn: Callable[..., Awaitable[Any]],
    ) -> None:
        tool = RegisteredTool(definition=definition, execute_fn=execute_fn)
        cls._tools[definition.name] = tool
        logger.debug(f"Registered tool: {definition.name}")

    @classmethod
    def get(cls, name: str) -> RegisteredTool:
        tool = cls._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(
                f"Tool '{name}' not found in registry. "
                f"Available: {list(cls._tools.keys())}"
            )
        return tool

    @classmethod
    def list_all(cls) -> list[RegisteredTool]:
        return list(cls._tools.values())

    @classmethod
    def list_descriptions(cls) -> list[dict[str, str]]:
        """Returns [{name, description}] for inclusion in orchestrator system prompts."""
        return [
            {"name": t.name, "description": t.description}
            for t in cls._tools.values()
        ]

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._tools
