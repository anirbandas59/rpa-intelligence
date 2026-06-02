"""
Unit tests for the Tool Registry infrastructure.

Tests cover:
- Registration and retrieval of tools
- ToolNotFoundError on unknown tool lookup
- list_descriptions() format
- is_registered() True/False
- RegisteredTool.execute() delegates to the underlying async function

No DB setup required — all execute functions are mocked.
"""

import pytest
from pydantic import BaseModel

from tools.registry import RegisteredTool, ToolDefinition, ToolNotFoundError, ToolRegistry

# ---------------------------------------------------------------------------
# Minimal Pydantic schemas for test tools
# ---------------------------------------------------------------------------

class _DummyInput(BaseModel):
    value: str


class _DummyOutput(BaseModel):
    result: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_definition(name: str, description: str = "A test tool") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        input_schema=_DummyInput,
        output_schema=_DummyOutput,
    )


async def _dummy_execute(value: str) -> _DummyOutput:
    return _DummyOutput(result=f"processed:{value}")


# ---------------------------------------------------------------------------
# Fixtures — isolate registry state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_registry():
    """Reset the ToolRegistry._tools dict before and after every test."""
    ToolRegistry._tools.clear()
    yield
    ToolRegistry._tools.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestToolRegistryRegisterAndGet:
    def test_register_adds_tool(self):
        defn = _make_definition("my_tool")
        ToolRegistry.register(defn, _dummy_execute)
        assert ToolRegistry.is_registered("my_tool")

    def test_get_returns_registered_tool(self):
        defn = _make_definition("my_tool")
        ToolRegistry.register(defn, _dummy_execute)
        tool = ToolRegistry.get("my_tool")
        assert isinstance(tool, RegisteredTool)
        assert tool.name == "my_tool"

    def test_get_returns_correct_description(self):
        defn = _make_definition("my_tool", description="Does something useful")
        ToolRegistry.register(defn, _dummy_execute)
        tool = ToolRegistry.get("my_tool")
        assert tool.description == "Does something useful"

    def test_register_multiple_tools(self):
        ToolRegistry.register(_make_definition("tool_a"), _dummy_execute)
        ToolRegistry.register(_make_definition("tool_b"), _dummy_execute)
        assert ToolRegistry.is_registered("tool_a")
        assert ToolRegistry.is_registered("tool_b")

    def test_register_overwrites_existing_tool(self):
        """Re-registering a tool under the same name replaces it silently."""
        ToolRegistry.register(_make_definition("tool_x", "original"), _dummy_execute)

        async def new_fn(**kwargs):
            return _DummyOutput(result="new")

        ToolRegistry.register(_make_definition("tool_x", "updated"), new_fn)
        tool = ToolRegistry.get("tool_x")
        assert tool.description == "updated"


class TestToolRegistryNotFound:
    def test_get_raises_tool_not_found_error(self):
        with pytest.raises(ToolNotFoundError) as exc_info:
            ToolRegistry.get("nonexistent_tool")
        assert "nonexistent_tool" in str(exc_info.value)

    def test_error_message_lists_available_tools(self):
        ToolRegistry.register(_make_definition("known_tool"), _dummy_execute)
        with pytest.raises(ToolNotFoundError) as exc_info:
            ToolRegistry.get("missing_tool")
        assert "known_tool" in str(exc_info.value)

    def test_tool_not_found_error_is_rpa_base_error(self):
        from core.exceptions import RPABaseError
        with pytest.raises(RPABaseError):
            ToolRegistry.get("anything")


class TestToolRegistryListDescriptions:
    def test_empty_registry_returns_empty_list(self):
        result = ToolRegistry.list_descriptions()
        assert result == []

    def test_list_descriptions_format(self):
        ToolRegistry.register(_make_definition("tool_a", "Alpha tool"), _dummy_execute)
        ToolRegistry.register(_make_definition("tool_b", "Beta tool"), _dummy_execute)
        descs = ToolRegistry.list_descriptions()
        assert len(descs) == 2
        for item in descs:
            assert "name" in item
            assert "description" in item
            assert isinstance(item["name"], str)
            assert isinstance(item["description"], str)

    def test_list_descriptions_values_match_registered(self):
        ToolRegistry.register(_make_definition("alpha", "Alpha description"), _dummy_execute)
        descs = ToolRegistry.list_descriptions()
        assert descs[0]["name"] == "alpha"
        assert descs[0]["description"] == "Alpha description"

    def test_list_all_returns_registered_tool_instances(self):
        ToolRegistry.register(_make_definition("tool_a"), _dummy_execute)
        ToolRegistry.register(_make_definition("tool_b"), _dummy_execute)
        all_tools = ToolRegistry.list_all()
        assert len(all_tools) == 2
        assert all(isinstance(t, RegisteredTool) for t in all_tools)


class TestIsRegistered:
    def test_returns_false_for_unknown_tool(self):
        assert ToolRegistry.is_registered("ghost") is False

    def test_returns_true_after_registration(self):
        ToolRegistry.register(_make_definition("real_tool"), _dummy_execute)
        assert ToolRegistry.is_registered("real_tool") is True

    def test_returns_false_after_registry_cleared(self):
        ToolRegistry.register(_make_definition("temp_tool"), _dummy_execute)
        ToolRegistry._tools.clear()
        assert ToolRegistry.is_registered("temp_tool") is False


class TestRegisteredToolExecute:
    @pytest.mark.asyncio
    async def test_execute_calls_underlying_function(self):
        called_with = {}

        async def capture_fn(**kwargs):
            called_with.update(kwargs)
            return _DummyOutput(result="ok")

        defn = _make_definition("capture_tool")
        ToolRegistry.register(defn, capture_fn)
        tool = ToolRegistry.get("capture_tool")
        await tool.execute(value="hello")
        assert called_with == {"value": "hello"}

    @pytest.mark.asyncio
    async def test_execute_returns_function_output(self):
        async def fn(**kwargs):
            return _DummyOutput(result="returned_value")

        ToolRegistry.register(_make_definition("result_tool"), fn)
        tool = ToolRegistry.get("result_tool")
        result = await tool.execute()
        assert result.result == "returned_value"

    @pytest.mark.asyncio
    async def test_execute_passes_all_kwargs(self):
        received = {}

        async def multi_kwarg_fn(**kwargs):
            received.update(kwargs)
            return _DummyOutput(result="multi")

        ToolRegistry.register(_make_definition("multi_tool"), multi_kwarg_fn)
        tool = ToolRegistry.get("multi_tool")
        await tool.execute(a=1, b="two", c=True)
        assert received == {"a": 1, "b": "two", "c": True}
