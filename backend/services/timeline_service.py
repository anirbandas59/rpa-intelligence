"""
Stage 3 (Delivery Timeline) service for deterministic phase calculation.

Pure Python implementation (zero LLM calls) that calculates six delivery phases
from effort estimate, start date, and complexity class. Applies complexity-adjusted
buffers for Design and UAT phases, and supports user-defined phase adjustments.

Key features:
- Deterministic calculation: same inputs → same output (no AI variability)
- Six-phase SDLC model: Define → Design → Build → SIT → UAT → Deploy
- Complexity-adjusted buffers: Design and UAT scale with complexity class
- User adjustments: phase_deltas allow manual tweaks to individual phases
- Business week calculations: uses 7-day weeks for calendar accuracy

Phase structure:
- Define: Fixed 1 week (requirements gathering)
- Design: Complexity-adjusted (S/M: 1wk, L/XL: 2wk)
- Build: User-provided effort_weeks (includes unit testing)
- SIT: Fixed 1 week (system integration testing)
- UAT: Complexity-adjusted (S/M: 1wk, L/XL: 2wk)
- Deploy: Fixed 1 week (production deployment)

Default buffers are defined in DEFAULT_BUFFERS constant.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel

DEFAULT_BUFFERS = {
    "define": {"weeks": 1, "complexity_adjusted": False},
    "design": {"S": 1, "M": 1, "L": 2, "XL": 2, "XS": 1},
    "sit": {"weeks": 1, "complexity_adjusted": False},
    "uat": {"S": 1, "M": 1, "L": 2, "XL": 2, "XS": 1},
    "deploy": {"weeks": 1, "complexity_adjusted": False},
}


@dataclass
class Phase:
    """
    Internal representation of a single delivery phase.

    Used during timeline calculation before converting to dict for API response.
    """

    name: str
    start_date: date
    end_date: date
    weeks: int
    is_delta: bool = False  # True if this phase has user adjustment applied


class TimelineResult(BaseModel):
    """
    Timeline calculation result with six phases and project end date.

    Returned by calculate_timeline() and stored in StageRun.result for Stage 3.
    """

    phases: list[dict] = []  # List of phase dicts with name, start_date, end_date, weeks, is_delta
    total_weeks: int  # Sum of all phase weeks
    project_end_date: str  # ISO format date string (last phase end_date)


def calculate_timeline(
    build_weeks: int,
    start_date: date,
    complexity_class: str = "M",
    buffers: dict | None = None,
    phase_deltas: dict | None = None,
) -> TimelineResult:
    """
    Calculate six-phase delivery timeline using pure Python (no LLM calls).

    Deterministic calculation that produces consistent results for same inputs.
    Applies complexity-adjusted buffers to Design and UAT phases, and supports
    user-defined adjustments via phase_deltas.

    Args:
        build_weeks: Effort estimate for Build phase (includes unit testing)
        start_date: Project start date (Define phase begins here)
        complexity_class: Complexity classification (XS/S/M/L/XL) affecting Design/UAT buffers
        buffers: Optional override for default buffer configuration
        phase_deltas: Optional user adjustments per phase (e.g., {"build": 2, "sit": -1})

    Returns:
        TimelineResult with phases list, total_weeks, and project_end_date

    Phase sequence:
        Define (1wk) → Design (1-2wk) → Build (user input) → SIT (1wk) → UAT (1-2wk) → Deploy (1wk)
    """
    b = buffers or {}
    deltas = phase_deltas or {}

    def buf(phase_name: str) -> int:
        """
        Get buffer weeks for a phase with complexity adjustment and user deltas.

        Fixed phases (define, sit, deploy) use static buffer values. Complexity-adjusted
        phases (design, uat) scale buffer based on complexity class. User deltas are
        applied after base buffer, with minimum of 1 week enforced.

        Args:
            phase_name: Phase name (define, design, sit, uat, deploy)

        Returns:
            Buffer weeks with complexity adjustment and user deltas applied
        """
        if phase_name in ("define", "sit", "deploy"):
            # Fixed buffer phases
            base = b.get(phase_name, DEFAULT_BUFFERS[phase_name]["weeks"])
        else:
            # Complexity-adjusted phases (design, uat)
            default_map = DEFAULT_BUFFERS[phase_name]
            base = b.get(phase_name, default_map.get(complexity_class, 1))

        # Apply user delta from phase adjustments
        delta = deltas.get(phase_name.lower(), 0)
        return max(1, base + delta)  # Minimum 1 week enforced

    phases = []
    cursor = start_date

    phase_configs = [
        ("define", buf("define")),
        ("design", buf("design")),
        ("build", build_weeks + deltas.get("build", 0)),
        ("sit", buf("sit")),
        ("uat", buf("uat")),
        ("deploy", buf("deploy")),
    ]

    for name, weeks in phase_configs:
        if weeks < 1:
            weeks = 1
        end = cursor + timedelta(weeks=weeks) - timedelta(days=1)
        phases.append(
            Phase(
                name=name.capitalize(),
                start_date=cursor,
                end_date=end,
                weeks=weeks,
                is_delta=name in deltas,
            )
        )
        cursor = end + timedelta(days=1)

    total_weeks = sum(p.weeks for p in phases)

    return TimelineResult(
        phases=[
            {
                "name": p.name,
                "start_date": p.start_date.isoformat(),
                "end_date": p.end_date.isoformat(),
                "weeks": p.weeks,
                "is_delta": p.is_delta,
            }
            for p in phases
        ],
        total_weeks=total_weeks,
        project_end_date=phases[-1].end_date.isoformat(),
    )
