"""
Stage 3 timeline service — pure Python, zero LLM.
Calculates delivery phases from effort_weeks + start_date + complexity_class.
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
    name: str
    start_date: date
    end_date: date
    weeks: int
    is_delta: bool = False


class TimelineResult(BaseModel):
    phases: list[dict]
    total_weeks: int
    project_end_date: str


def calculate_timeline(
    build_weeks: int,
    start_date: date,
    complexity_class: str = "M",
    buffers: dict | None = None,
    phase_deltas: dict | None = None,
) -> TimelineResult:
    """Pure Python. Zero LLM. Returns phases list.

    Args:
        build_weeks: Effort weeks for Build + Unit Testing phase
        start_date: Project start date
        complexity_class: XS|S|M|L|XL — affects Design and UAT buffers
        buffers: Override default buffer configuration
        phase_deltas: User adjustments per phase (phase_name: delta_weeks)
    """
    b = buffers or {}
    deltas = phase_deltas or {}

    def buf(phase_name: str) -> int:
        """Get buffer weeks for a phase, applying complexity and user deltas."""
        if phase_name in ("define", "sit", "deploy"):
            base = b.get(phase_name, DEFAULT_BUFFERS[phase_name]["weeks"])
        else:
            # complexity-adjusted phases (design, uat)
            default_map = DEFAULT_BUFFERS[phase_name]
            base = b.get(phase_name, default_map.get(complexity_class, 1))

        # Apply user delta
        delta = deltas.get(phase_name.lower(), 0)
        return max(1, base + delta)  # minimum 1 week

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
            Phase(name=name.capitalize(), start_date=cursor, end_date=end, weeks=weeks, is_delta=name in deltas)
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
