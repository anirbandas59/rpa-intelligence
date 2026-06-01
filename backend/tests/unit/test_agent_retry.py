"""
Unit tests for process_agent.py and tracker_agent.py retry/validation loops.

Tests that:
- retry_count increments when LLM returns invalid output
- retry_hint is included in the second prompt call
- final state contains a valid result after successful retry
- AgentExecutionError raised when retries exhausted
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agents.process_agent as pa
import agents.tracker_agent as ta

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

VALID_BANDS_JSON = json.dumps(
    {
        "activities": "M",
        "business_rules": "L",
        "layouts": "S",
        "interfaces": "XS",
        "technology": "XL",
        "extraction_notes": "High confidence extraction.",
    }
)

INVALID_BANDS_JSON = json.dumps(
    {
        "activities": "MEDIUM",  # invalid band value
        "business_rules": "L",
        "layouts": "S",
        "interfaces": "XS",
        "technology": "XL",
        "extraction_notes": "First attempt.",
    }
)

VALID_FEATURES_JSON = json.dumps(
    {
        "features": [
            {
                "name": "Login Automation",
                "description": "Automate login flow",
                "size": "S",
                "dependencies": [],
            },
            {
                "name": "Data Extraction",
                "description": "Extract table rows",
                "size": "M",
                "dependencies": [],
            },
        ],
        "summary": "Two core features identified.",
    }
)

INVALID_FEATURES_JSON = json.dumps(
    {
        "features": [
            {
                "name": "Bad Feature",
                "description": "Invalid size band",
                "size": "HUGE",  # invalid band value
                "dependencies": [],
            }
        ],
        "summary": "One feature.",
    }
)


def _make_mock_sprint_result() -> MagicMock:
    result = MagicMock()
    result.sprint_plans = []
    result.sprint_summaries = {}
    result.total_points = 0
    result.warnings = []
    return result


# ──────────────────────────────────────────────
# process_agent — node-level unit tests
# ──────────────────────────────────────────────


class TestProcessAgentNodes:
    """Test individual nodes of the process agent state machine."""

    @pytest.mark.asyncio
    async def test_extract_bands_node_no_hint(self) -> None:
        """extract_bands_node calls LLM once and stores raw bands dict."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_BANDS_JSON)

        state: pa.ProcessState = {
            "document_text": "Some process doc.",
            "model": "claude-haiku-4-5",
            "bands": None,
            "extraction_notes": "",
            "retry_count": 0,
            "retry_hint": None,
            "error": None,
            "result": None,
        }

        with patch("agents.process_agent.get_default_manager", return_value=mock_manager):
            new_state = await pa.extract_bands_node(state)

        assert new_state["bands"]["activities"] == "M"
        assert "Previous attempt was invalid" not in mock_manager.complete_async.call_args[1].get(
            "prompt", ""
        )

    @pytest.mark.asyncio
    async def test_extract_bands_node_injects_retry_hint(self) -> None:
        """When retry_hint is set, the hint is appended to the user prompt."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_BANDS_JSON)

        state: pa.ProcessState = {
            "document_text": "Some process doc.",
            "model": "claude-haiku-4-5",
            "bands": None,
            "extraction_notes": "",
            "retry_count": 1,
            "retry_hint": "Fix band values: Invalid band for 'activities': 'MEDIUM'.",
            "error": None,
            "result": None,
        }

        with patch("agents.process_agent.get_default_manager", return_value=mock_manager):
            await pa.extract_bands_node(state)

        call_kwargs = mock_manager.complete_async.call_args[1]
        assert "Previous attempt was invalid" in call_kwargs["prompt"]
        assert "Fix band values" in call_kwargs["prompt"]

    def test_validate_bands_node_sets_result_on_valid(self) -> None:
        """validate_bands_node sets state['result'] when bands are valid."""
        state: pa.ProcessState = {
            "document_text": "doc",
            "model": "claude-haiku-4-5",
            "bands": {
                "activities": "M",
                "business_rules": "L",
                "layouts": "S",
                "interfaces": "XS",
                "technology": "XL",
            },
            "extraction_notes": "",
            "retry_count": 0,
            "retry_hint": None,
            "error": None,
            "result": None,
        }

        new_state = pa.validate_bands_node(state)

        assert new_state["result"] is not None
        assert new_state["result"].activities == "M"

    def test_validate_bands_node_increments_retry_on_failure(self) -> None:
        """validate_bands_node increments retry_count and sets retry_hint on bad bands."""
        state: pa.ProcessState = {
            "document_text": "doc",
            "model": "claude-haiku-4-5",
            "bands": {
                "activities": "MEDIUM",  # invalid
                "business_rules": "L",
                "layouts": "S",
                "interfaces": "XS",
                "technology": "XL",
            },
            "extraction_notes": "",
            "retry_count": 0,
            "retry_hint": None,
            "error": None,
            "result": None,
        }

        new_state = pa.validate_bands_node(state)

        assert new_state["retry_count"] == 1
        assert new_state["retry_hint"] is not None
        assert new_state["result"] is None

    def test_validate_bands_node_raises_after_max_retries(self) -> None:
        """validate_bands_node raises AgentExecutionError when retry_count >= 2."""
        from core.exceptions import AgentExecutionError

        state: pa.ProcessState = {
            "document_text": "doc",
            "model": "claude-haiku-4-5",
            "bands": {
                "activities": "MEDIUM",  # still invalid
                "business_rules": "L",
                "layouts": "S",
                "interfaces": "XS",
                "technology": "XL",
            },
            "extraction_notes": "",
            "retry_count": 2,  # already at limit
            "retry_hint": "Previous hint",
            "error": None,
            "result": None,
        }

        with pytest.raises(AgentExecutionError):
            pa.validate_bands_node(state)

    def test_route_validate_returns_end_on_result(self) -> None:
        """route_validate returns 'end' when result is set."""
        from core.models.scoring import AttributeBandsWithSource

        state: pa.ProcessState = {
            "document_text": "doc",
            "model": "m",
            "bands": {},
            "extraction_notes": "",
            "retry_count": 0,
            "retry_hint": None,
            "error": None,
            "result": AttributeBandsWithSource(
                activities="M",
                business_rules="S",
                layouts="XS",
                interfaces="XS",
                technology="S",
            ),
        }
        assert pa.route_validate(state) == "end"

    def test_route_validate_returns_retry_when_hint_set(self) -> None:
        """route_validate returns 'retry' when retry_hint is set and count < 2."""
        state: pa.ProcessState = {
            "document_text": "doc",
            "model": "m",
            "bands": {"activities": "MEDIUM"},
            "extraction_notes": "",
            "retry_count": 1,
            "retry_hint": "Fix band values: ...",
            "error": None,
            "result": None,
        }
        assert pa.route_validate(state) == "retry"


# ──────────────────────────────────────────────
# process_agent — full graph integration
# ──────────────────────────────────────────────


class TestProcessAgentGraph:
    @pytest.mark.asyncio
    async def test_first_call_valid_no_retry(self) -> None:
        """When the first LLM response is valid, result returned with one LLM call."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_BANDS_JSON)

        with patch("agents.process_agent.get_default_manager", return_value=mock_manager):
            result = await pa.extract_bands_from_text("Some document text.")

        assert result.activities == "M"
        assert result.business_rules == "L"
        assert result.activities_source == "ai_extracted"
        assert mock_manager.complete_async.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_count_increments_on_invalid_response(self) -> None:
        """When first response is invalid, retries once and succeeds."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(
            side_effect=[INVALID_BANDS_JSON, VALID_BANDS_JSON]
        )

        with patch("agents.process_agent.get_default_manager", return_value=mock_manager):
            result = await pa.extract_bands_from_text("Some document text.")

        assert result.activities == "M"
        assert mock_manager.complete_async.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_hint_appears_in_second_prompt(self) -> None:
        """The second LLM call must include the retry hint from QualityEvaluator."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(
            side_effect=[INVALID_BANDS_JSON, VALID_BANDS_JSON]
        )

        with patch("agents.process_agent.get_default_manager", return_value=mock_manager):
            await pa.extract_bands_from_text("Some document text.")

        assert mock_manager.complete_async.call_count == 2
        second_call_kwargs = mock_manager.complete_async.call_args_list[1][1]
        second_prompt = second_call_kwargs.get("prompt", "")
        assert "Previous attempt was invalid" in second_prompt

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """When all retries are exhausted (3 LLM calls), AgentExecutionError is raised."""
        from core.exceptions import AgentExecutionError

        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=INVALID_BANDS_JSON)

        with patch("agents.process_agent.get_default_manager", return_value=mock_manager):
            with pytest.raises(AgentExecutionError):
                await pa.extract_bands_from_text("Some document text.")

        # initial + 2 retries = 3 total calls
        assert mock_manager.complete_async.call_count == 3


# ──────────────────────────────────────────────
# tracker_agent — node-level unit tests
# ──────────────────────────────────────────────


class TestTrackerAgentNodes:
    """Test individual nodes of the tracker agent state machine."""

    @pytest.mark.asyncio
    async def test_decompose_features_no_hint(self) -> None:
        """decompose_features_node calls LLM and parses features without hint."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_FEATURES_JSON)

        state: ta.TrackerState = {
            "use_case_id": "uc-1",
            "process_name": "Test Process",
            "process_description": "Automate something",
            "complexity_class": "M",
            "effort_weeks": 5,
            "sprint_count": 3,
            "sprint_capacity": 8,
            "document_context": "Process Overview: Automate something",
            "raw_llm_response": "",
            "extracted_features": [],
            "sprint_assignment": {},
            "error": None,
            "retry_count": 0,
            "retry_hint": None,
        }

        with patch("agents.tracker_agent.get_default_manager", return_value=mock_manager):
            new_state = await ta.decompose_features_node(state)

        assert len(new_state["extracted_features"]) == 2
        call_kwargs = mock_manager.complete_async.call_args[1]
        assert "Previous attempt failed validation" not in call_kwargs.get("prompt", "")

    @pytest.mark.asyncio
    async def test_decompose_features_injects_retry_hint(self) -> None:
        """decompose_features_node appends retry hint when set."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_FEATURES_JSON)

        state: ta.TrackerState = {
            "use_case_id": "uc-1",
            "process_name": "Test Process",
            "process_description": "Automate something",
            "complexity_class": "M",
            "effort_weeks": 5,
            "sprint_count": 3,
            "sprint_capacity": 8,
            "document_context": "Process Overview: Automate something",
            "raw_llm_response": "",
            "extracted_features": [],
            "sprint_assignment": {},
            "error": None,
            "retry_count": 1,
            "retry_hint": "Fix features list: Feature 0 has invalid size: 'HUGE'",
        }

        with patch("agents.tracker_agent.get_default_manager", return_value=mock_manager):
            await ta.decompose_features_node(state)

        call_kwargs = mock_manager.complete_async.call_args[1]
        assert "Previous attempt failed validation" in call_kwargs["prompt"]
        assert "Fix features list" in call_kwargs["prompt"]

    def test_validate_features_passes_on_valid(self) -> None:
        """validate_features_node passes without modifying state when features are valid."""
        state: ta.TrackerState = {
            "use_case_id": "uc-1",
            "process_name": "Test",
            "process_description": "desc",
            "complexity_class": "M",
            "effort_weeks": 5,
            "sprint_count": 3,
            "sprint_capacity": 8,
            "document_context": "",
            "raw_llm_response": "",
            "extracted_features": [
                {"name": "F1", "size": "S", "description": "d1"},
                {"name": "F2", "size": "M", "description": "d2"},
            ],
            "sprint_assignment": {},
            "error": None,
            "retry_count": 0,
            "retry_hint": None,
        }

        new_state = ta.validate_features_node(state)
        # No change to retry_count or hint on pass
        assert new_state["retry_count"] == 0
        assert new_state.get("retry_hint") is None

    def test_validate_features_increments_retry_on_invalid(self) -> None:
        """validate_features_node increments retry_count and sets retry_hint on bad features."""
        state: ta.TrackerState = {
            "use_case_id": "uc-1",
            "process_name": "Test",
            "process_description": "desc",
            "complexity_class": "M",
            "effort_weeks": 5,
            "sprint_count": 3,
            "sprint_capacity": 8,
            "document_context": "",
            "raw_llm_response": "",
            "extracted_features": [
                {"name": "Bad", "size": "HUGE", "description": "invalid"},
            ],
            "sprint_assignment": {},
            "error": None,
            "retry_count": 0,
            "retry_hint": None,
        }

        new_state = ta.validate_features_node(state)
        assert new_state["retry_count"] == 1
        assert new_state["retry_hint"] is not None

    def test_validate_features_raises_after_max_retries(self) -> None:
        """validate_features_node raises AgentExecutionError when retry_count >= 2."""
        from core.exceptions import AgentExecutionError

        state: ta.TrackerState = {
            "use_case_id": "uc-1",
            "process_name": "Test",
            "process_description": "desc",
            "complexity_class": "M",
            "effort_weeks": 5,
            "sprint_count": 3,
            "sprint_capacity": 8,
            "document_context": "",
            "raw_llm_response": "",
            "extracted_features": [
                {"name": "Bad", "size": "HUGE", "description": "still invalid"},
            ],
            "sprint_assignment": {},
            "error": None,
            "retry_count": 2,  # already at limit
            "retry_hint": "previous hint",
        }

        with pytest.raises(AgentExecutionError):
            ta.validate_features_node(state)


# ──────────────────────────────────────────────
# tracker_agent — full graph integration
# ──────────────────────────────────────────────


class TestTrackerAgentGraph:
    @pytest.mark.asyncio
    async def test_valid_features_no_retry(self) -> None:
        """When first LLM response has valid features, sprint assignment runs with 1 LLM call."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_FEATURES_JSON)

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
            patch(
                "agents.tracker_agent.assign_sprints",
                return_value=_make_mock_sprint_result(),
            ),
        ):
            result = await ta.run_tracker_agent(
                use_case_id="uc-001",
                process_name="Invoice Processing",
                process_description="Automate invoice workflow",
                complexity_class="M",
                effort_weeks=5,
                sprint_count=3,
            )

        assert result["features"] is not None
        assert mock_manager.complete_async.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_count_increments_on_invalid_features(self) -> None:
        """When first LLM response has invalid features, retry fires and second succeeds."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(
            side_effect=[INVALID_FEATURES_JSON, VALID_FEATURES_JSON]
        )

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
            patch(
                "agents.tracker_agent.assign_sprints",
                return_value=_make_mock_sprint_result(),
            ),
        ):
            result = await ta.run_tracker_agent(
                use_case_id="uc-002",
                process_name="HR Onboarding",
                process_description="Automate HR onboarding steps",
                complexity_class="S",
                effort_weeks=3,
                sprint_count=2,
            )

        assert mock_manager.complete_async.call_count == 2
        assert result["metadata"]["retry_count"] >= 1

    @pytest.mark.asyncio
    async def test_retry_hint_appears_in_second_decompose_prompt(self) -> None:
        """The second decompose call must contain the retry hint."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(
            side_effect=[INVALID_FEATURES_JSON, VALID_FEATURES_JSON]
        )

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
            patch(
                "agents.tracker_agent.assign_sprints",
                return_value=_make_mock_sprint_result(),
            ),
        ):
            await ta.run_tracker_agent(
                use_case_id="uc-003",
                process_name="Claim Processing",
                process_description="Insurance claim automation",
                complexity_class="L",
                effort_weeks=6,
                sprint_count=4,
            )

        assert mock_manager.complete_async.call_count == 2
        second_call_kwargs = mock_manager.complete_async.call_args_list[1][1]
        second_prompt = second_call_kwargs.get("prompt", "")
        assert "Previous attempt failed validation" in second_prompt

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """When all retries exhausted (3 calls total), AgentExecutionError is raised."""
        from core.exceptions import AgentExecutionError

        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=INVALID_FEATURES_JSON)

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
            patch("agents.tracker_agent.assign_sprints"),
        ):
            with pytest.raises(AgentExecutionError):
                await ta.run_tracker_agent(
                    use_case_id="uc-004",
                    process_name="Payroll",
                    process_description="Automate payroll",
                    complexity_class="M",
                    effort_weeks=5,
                    sprint_count=3,
                )

        assert mock_manager.complete_async.call_count == 3
