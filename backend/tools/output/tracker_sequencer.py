"""Pure Python date sequencer for tracker rows."""

import logging
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TrackerRow(BaseModel):
    feature: str
    hours: float
    priority: Literal["MUST", "SHOULD"]


class SequencedRow(BaseModel):
    feature: str
    hours: float
    priority: Literal["MUST", "SHOULD"]
    start_date: date
    end_date: date


class SequencerInput(BaseModel):
    tracker_rows: list[TrackerRow]
    build_sit_start: date
    build_sit_end: date
    total_effort_hours: float


def sequence_dates(input: SequencerInput) -> list[SequencedRow]:
    """
    Assign sequential calendar dates to tracker rows within Build+SIT window.

    Logic:
    - Total calendar days = (build_sit_end - build_sit_start).days
    - Each row gets proportional allocation:
      row_days = round((row.hours / total_effort_hours) * total_calendar_days)
    - Assign start_date = previous row's end_date + 1 day
    - First row start = build_sit_start
    """
    total_calendar_days = (input.build_sit_end - input.build_sit_start).days

    if total_calendar_days <= 0:
        raise ValueError("build_sit_end must be after build_sit_start")

    if input.total_effort_hours <= 0:
        raise ValueError("total_effort_hours must be positive")

    sequenced_rows = []
    current_date = input.build_sit_start

    for idx, row in enumerate(input.tracker_rows):
        # Calculate proportional days for this row
        proportion = row.hours / input.total_effort_hours
        row_days = max(1, round(proportion * total_calendar_days))

        # Last row gets remaining days to ensure we end exactly on build_sit_end
        if idx == len(input.tracker_rows) - 1:
            end_date = input.build_sit_end
        else:
            end_date = current_date + timedelta(days=row_days - 1)

        sequenced_rows.append(
            SequencedRow(
                feature=row.feature,
                hours=row.hours,
                priority=row.priority,
                start_date=current_date,
                end_date=end_date,
            )
        )

        # Next row starts the day after this row ends
        current_date = end_date + timedelta(days=1)

    logger.info(
        f"Sequenced {len(sequenced_rows)} rows across {total_calendar_days} days "
        f"({input.build_sit_start} to {input.build_sit_end})"
    )

    return sequenced_rows
