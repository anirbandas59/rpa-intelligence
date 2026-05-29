"""
Unit tests for Stage 3 timeline service — pure Python timeline calculation.
"""

from datetime import date, timedelta
from services.timeline_service import calculate_timeline


def test_basic_timeline_calculation():
    """Test basic timeline with default buffers."""
    result = calculate_timeline(build_weeks=6, start_date=date(2025, 7, 1), complexity_class="M")

    # Define(1) + Design(1) + Build(6) + SIT(1) + UAT(1) + Deploy(1) = 11 weeks
    assert result.total_weeks == 11
    assert len(result.phases) == 6
    assert result.phases[0]["name"] == "Define"
    assert result.phases[2]["name"] == "Build"


def test_complexity_adjusted_phases():
    """Test that Design and UAT phases adjust based on complexity class."""
    # L complexity should have 2-week Design and UAT
    result_l = calculate_timeline(build_weeks=6, start_date=date(2025, 7, 1), complexity_class="L")

    design_phase = next(p for p in result_l.phases if p["name"] == "Design")
    uat_phase = next(p for p in result_l.phases if p["name"] == "Uat")

    assert design_phase["weeks"] == 2
    assert uat_phase["weeks"] == 2

    # S complexity should have 1-week Design and UAT
    result_s = calculate_timeline(build_weeks=6, start_date=date(2025, 7, 1), complexity_class="S")

    design_phase_s = next(p for p in result_s.phases if p["name"] == "Design")
    uat_phase_s = next(p for p in result_s.phases if p["name"] == "Uat")

    assert design_phase_s["weeks"] == 1
    assert uat_phase_s["weeks"] == 1


def test_phase_deltas():
    """Test that phase deltas are applied correctly."""
    result = calculate_timeline(
        build_weeks=6,
        start_date=date(2025, 7, 1),
        complexity_class="M",
        phase_deltas={"build": 2, "uat": -1},  # Add 2 weeks to build, subtract 1 from UAT
    )

    build_phase = next(p for p in result.phases if p["name"] == "Build")
    uat_phase = next(p for p in result.phases if p["name"] == "Uat")

    assert build_phase["weeks"] == 8  # 6 + 2
    assert build_phase["is_delta"] is True
    # UAT minimum is 1 week, so -1 from default 1 should still be 1
    assert uat_phase["weeks"] >= 1


def test_custom_buffers():
    """Test custom buffer configuration."""
    custom_buffers = {
        "define": 2,  # Override to 2 weeks
        "deploy": 2,  # Override to 2 weeks
    }

    result = calculate_timeline(
        build_weeks=6, start_date=date(2025, 7, 1), complexity_class="M", buffers=custom_buffers
    )

    define_phase = next(p for p in result.phases if p["name"] == "Define")
    deploy_phase = next(p for p in result.phases if p["name"] == "Deploy")

    assert define_phase["weeks"] == 2
    assert deploy_phase["weeks"] == 2


def test_date_continuity():
    """Test that phases are continuous with no gaps."""
    result = calculate_timeline(build_weeks=4, start_date=date(2025, 1, 1), complexity_class="M")

    for i in range(len(result.phases) - 1):
        current_end = date.fromisoformat(result.phases[i]["end_date"])
        next_start = date.fromisoformat(result.phases[i + 1]["start_date"])
        # Next phase should start the day after current phase ends
        assert next_start == current_end + timedelta(days=1)


def test_project_end_date():
    """Test that project_end_date matches the last phase end date."""
    result = calculate_timeline(build_weeks=6, start_date=date(2025, 7, 1), complexity_class="M")

    last_phase_end = result.phases[-1]["end_date"]
    assert result.project_end_date == last_phase_end


def test_xl_complexity():
    """Test XL complexity with extended Design and UAT buffers."""
    result = calculate_timeline(build_weeks=8, start_date=date(2025, 1, 1), complexity_class="XL")

    design_phase = next(p for p in result.phases if p["name"] == "Design")
    uat_phase = next(p for p in result.phases if p["name"] == "Uat")

    assert design_phase["weeks"] == 2
    assert uat_phase["weeks"] == 2


def test_xs_complexity():
    """Test XS complexity with minimal buffers."""
    result = calculate_timeline(build_weeks=1, start_date=date(2025, 1, 1), complexity_class="XS")

    design_phase = next(p for p in result.phases if p["name"] == "Design")
    uat_phase = next(p for p in result.phases if p["name"] == "Uat")

    assert design_phase["weeks"] == 1
    assert uat_phase["weeks"] == 1
