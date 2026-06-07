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
        """route_validate returns 'reflexion' when result is set."""
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
        assert pa.route_validate(state) == "reflexion"

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

VALID_WBS_JSON = json.dumps({
    "wbs_rows": [
        {"feature": "F1", "hours": 100.0, "priority": "MUST"},
        {"feature": "F2", "hours": 100.0, "priority": "SHOULD"}
    ]
})

INVALID_WBS_JSON = json.dumps({
    "wbs_rows": [
        {"feature": "F1", "hours": 50.0, "priority": "MUST"}
    ]
})


class TestTrackerAgentNodes:
    """Test individual nodes of the tracker agent state machine."""

    @pytest.mark.asyncio
    async def test_group_steps_no_hint(self) -> None:
        """group_steps_node calls LLM and parses features without hint."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_WBS_JSON)

        state: ta.TrackerState = {
            "session_id": "test-session",
            "use_case_id": "uc-1",
            "process_name": "Test Process",
            "task_extraction": {"activities": []},
            "total_effort_hours": 200.0,
            "complexity_class": "M",
            "effort_weeks": 5,
            "build_sit_window": {"start_date": "2025-07-01", "end_date": "2025-08-15"},
            "sprint_count": 3,
            "sprint_capacity": 8,
            "raw_llm_response": "",
            "wbs_rows": [],
            "sequenced_rows": [],
            "error": None,
            "retry_count": 0,
            "retry_hint": None,
        }

        with patch("agents.tracker_agent.get_default_manager", return_value=mock_manager):
            new_state = await ta.group_steps_node(state)

        assert new_state["raw_llm_response"] == VALID_WBS_JSON
        call_kwargs = mock_manager.complete_async.call_args[1]
        assert "Previous attempt failed validation" not in call_kwargs.get("prompt", "")

    @pytest.mark.asyncio
    async def test_group_steps_injects_retry_hint(self) -> None:
        """group_steps_node appends retry hint when set."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_WBS_JSON)

        state: ta.TrackerState = {
            "session_id": "test-session",
            "use_case_id": "uc-1",
            "process_name": "Test Process",
            "task_extraction": {"activities": []},
            "total_effort_hours": 200.0,
            "complexity_class": "M",
            "effort_weeks": 5,
            "build_sit_window": {"start_date": "2025-07-01", "end_date": "2025-08-15"},
            "sprint_count": 3,
            "sprint_capacity": 8,
            "raw_llm_response": "",
            "wbs_rows": [],
            "sequenced_rows": [],
            "error": None,
            "retry_count": 1,
            "retry_hint": "The total hours was 50.00 but must equal 200.00. Regroup the steps to match.",
        }

        with patch("agents.tracker_agent.get_default_manager", return_value=mock_manager):
            await ta.group_steps_node(state)

        call_kwargs = mock_manager.complete_async.call_args[1]
        assert "Previous attempt failed validation" in call_kwargs["prompt"]
        assert "The total hours was 50.00" in call_kwargs["prompt"]

    def test_validate_sum_passes_on_valid(self) -> None:
        """validate_sum_node passes without modifying state when sum matches."""
        state: ta.TrackerState = {
            "session_id": "test-session",
            "use_case_id": "uc-1",
            "process_name": "Test",
            "task_extraction": {"activities": []},
            "total_effort_hours": 200.0,
            "complexity_class": "M",
            "effort_weeks": 5,
            "build_sit_window": {"start_date": "2025-07-01", "end_date": "2025-08-15"},
            "sprint_count": 3,
            "sprint_capacity": 8,
            "raw_llm_response": VALID_WBS_JSON,
            "wbs_rows": [],
            "sequenced_rows": [],
            "error": None,
            "retry_count": 0,
            "retry_hint": None,
        }

        new_state = {**state, **ta.validate_sum_node(state)}
        # No change to retry_count or hint on pass
        assert new_state["retry_count"] == 0
        assert new_state.get("retry_hint") is None
        assert len(new_state["wbs_rows"]) == 2

    def test_validate_sum_increments_retry_on_invalid(self) -> None:
        """validate_sum_node increments retry_count and sets retry_hint on bad sum."""
        state: ta.TrackerState = {
            "session_id": "test-session",
            "use_case_id": "uc-1",
            "process_name": "Test",
            "task_extraction": {"activities": []},
            "total_effort_hours": 200.0,
            "complexity_class": "M",
            "effort_weeks": 5,
            "build_sit_window": {"start_date": "2025-07-01", "end_date": "2025-08-15"},
            "sprint_count": 3,
            "sprint_capacity": 8,
            "raw_llm_response": INVALID_WBS_JSON,
            "wbs_rows": [],
            "sequenced_rows": [],
            "error": None,
            "retry_count": 0,
            "retry_hint": None,
        }

        new_state = {**state, **ta.validate_sum_node(state)}
        assert new_state["retry_count"] == 1
        assert new_state["retry_hint"] is not None
        assert not new_state.get("wbs_rows")

    def test_validate_sum_sets_error_after_max_retries(self) -> None:
        """validate_sum_node sets error in state when retry_count >= 2."""
        state: ta.TrackerState = {
            "session_id": "test-session",
            "use_case_id": "uc-1",
            "process_name": "Test",
            "task_extraction": {"activities": []},
            "total_effort_hours": 200.0,
            "complexity_class": "M",
            "effort_weeks": 5,
            "build_sit_window": {"start_date": "2025-07-01", "end_date": "2025-08-15"},
            "sprint_count": 3,
            "sprint_capacity": 8,
            "raw_llm_response": INVALID_WBS_JSON,
            "wbs_rows": [],
            "sequenced_rows": [],
            "error": None,
            "retry_count": 1,  # one previous retry, this will be the second attempt
            "retry_hint": "previous hint",
        }

        new_state = {**state, **ta.validate_sum_node(state)}
        assert new_state["retry_count"] == 2
        assert "validation failed" in new_state["error"].lower()


# ──────────────────────────────────────────────
# tracker_agent — full graph integration
# ──────────────────────────────────────────────

class TestTrackerAgentGraph:
    @pytest.mark.asyncio
    async def test_valid_wbs_no_retry(self) -> None:
        """When first LLM response has valid WBS, sequencer runs with 1 LLM call."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=VALID_WBS_JSON)

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
        ):
            result = await ta.run_tracker_agent(
                use_case_id="uc-001",
                process_name="Invoice Processing",
                task_extraction={"activities": []},
                total_effort_hours=200.0,
                build_sit_window={"start_date": "2025-07-01", "end_date": "2025-08-15"},
                complexity_class="M",
                effort_weeks=5,
                session_id="test-session",
            )

        assert len(result["wbs_rows"]) == 2
        assert len(result["sequenced_rows"]) == 2
        assert mock_manager.complete_async.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_count_increments_on_invalid_wbs(self) -> None:
        """When first LLM response has invalid WBS, retry fires and second succeeds."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(
            side_effect=[INVALID_WBS_JSON, VALID_WBS_JSON]
        )

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
        ):
            result = await ta.run_tracker_agent(
                use_case_id="uc-002",
                process_name="HR Onboarding",
                task_extraction={"activities": []},
                total_effort_hours=200.0,
                build_sit_window={"start_date": "2025-07-01", "end_date": "2025-08-15"},
                complexity_class="S",
                effort_weeks=3,
                session_id="test-session",
            )

        assert mock_manager.complete_async.call_count == 2
        assert result["metadata"]["retry_count"] >= 1

    @pytest.mark.asyncio
    async def test_retry_hint_appears_in_second_group_prompt(self) -> None:
        """The second grouping call must contain the retry hint."""
        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(
            side_effect=[INVALID_WBS_JSON, VALID_WBS_JSON]
        )

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
        ):
            await ta.run_tracker_agent(
                use_case_id="uc-003",
                process_name="Claim Processing",
                task_extraction={"activities": []},
                total_effort_hours=200.0,
                build_sit_window={"start_date": "2025-07-01", "end_date": "2025-08-15"},
                complexity_class="L",
                effort_weeks=6,
                session_id="test-session",
            )

        assert mock_manager.complete_async.call_count == 2
        second_call_kwargs = mock_manager.complete_async.call_args_list[1][1]
        second_prompt = second_call_kwargs.get("prompt", "")
        assert "Previous attempt failed validation" in second_prompt

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """When all retries exhausted (2 attempts total), AgentExecutionError is raised."""
        from core.exceptions import AgentExecutionError

        mock_manager = MagicMock()
        mock_manager.complete_async = AsyncMock(return_value=INVALID_WBS_JSON)

        with (
            patch("agents.tracker_agent.get_default_manager", return_value=mock_manager),
        ):
            with pytest.raises(AgentExecutionError):
                await ta.run_tracker_agent(
                    use_case_id="uc-004",
                    process_name="Payroll",
                    task_extraction={"activities": []},
                    total_effort_hours=200.0,
                    build_sit_window={"start_date": "2025-07-01", "end_date": "2025-08-15"},
                    complexity_class="M",
                    effort_weeks=5,
                    session_id="test-session",
                )

        assert mock_manager.complete_async.call_count == 2
