"""
Phase 4 exit condition test — verify timeline calculation meets requirements.

Requirements from IMPLEMENTATION_GUIDE.md Phase 4:
POST /s3/runs with effort_weeks=6, start_date=2025-07-01, complexity_class=L
Verify phases: Define 1wk, Design 2wks, Build 6wks, SIT 1wk, UAT 2wks, Deploy 1wk = 13wks total
"""

from datetime import date, timedelta

from services.timeline_service import calculate_timeline


def test_phase4_exit_condition():
    """
    Phase 4 exit condition: L complexity with 6 weeks effort.
    Expected: Define(1) + Design(2) + Build(6) + SIT(1) + UAT(2) + Deploy(1) = 13 weeks
    """
    result = calculate_timeline(build_weeks=6, start_date=date(2025, 7, 1), complexity_class="L")

    # Verify total weeks
    assert result.total_weeks == 13, f"Expected 13 weeks, got {result.total_weeks}"

    # Verify individual phases
    phases = {p["name"]: p for p in result.phases}

    assert phases["Define"]["weeks"] == 1
    assert phases["Design"]["weeks"] == 2  # L complexity → 2 weeks
    assert phases["Build"]["weeks"] == 6
    assert phases["Sit"]["weeks"] == 1
    assert phases["Uat"]["weeks"] == 2  # L complexity → 2 weeks
    assert phases["Deploy"]["weeks"] == 1

    # Verify start date
    assert phases["Define"]["start_date"] == "2025-07-01"

    # Verify phase continuity - Design should start after Define ends
    expected_design_start = (date(2025, 7, 1) + timedelta(weeks=1)).isoformat()
    assert phases["Design"]["start_date"] == expected_design_start

    print("✅ Phase 4 exit condition met:")
    print(f"   Total: {result.total_weeks} weeks")
    print(f"   End date: {result.project_end_date}")
    for phase in result.phases:
        print(
            f"   - {phase['name']}: {phase['weeks']}w ({phase['start_date']} to {phase['end_date']})"
        )


if __name__ == "__main__":
    from datetime import timedelta

    test_phase4_exit_condition()
