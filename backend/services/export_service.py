"""
Export service — generate Excel tracker from Stage 4 results using output_template.xlsx.
Writes formulas (not computed values) for SP and Dev Status columns.
"""

import io
import logging
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from tools.output.export_tool import FORMULA_SP, formula_dev_status

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "templates" / "output_template.xlsx"


def generate_tracker_xlsx(use_case_name: str, s2_result: dict, s3_result: dict, s4_result: dict) -> io.BytesIO:
    """
    Generate tracker Excel from output_template.xlsx.

    Args:
        use_case_name: Name of the use case
        s2_result: Stage 2 complexity result
        s3_result: Stage 3 timeline result
        s4_result: Stage 4 tracker result (with sequenced_rows)

    Returns:
        BytesIO buffer with Excel file content
    """
    logger.info(f"Generating tracker xlsx for '{use_case_name}'")

    # Load template (data_only=False to preserve formulas)
    wb = openpyxl.load_workbook(TEMPLATE_PATH, data_only=False)

    # Get the "Feature and delivery timeline" sheet
    ws = wb["Feature and delivery timeline"]

    # Write project metadata to rows 3-6
    _write_project_metadata(ws, use_case_name, s2_result, s3_result)

    # Write tracker rows starting at row 19
    _write_tracker_rows(ws, s4_result, use_case_name)

    # Save to buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    logger.info(f"Generated tracker xlsx with sequenced rows")
    return buffer


def _write_project_metadata(ws, use_case_name: str, s2_result: dict, s3_result: dict):
    """Write project metadata to rows 3-6 (verify cell addresses from template)."""
    # Row 3: PROJECT TITLE
    ws["C3"] = use_case_name

    # Row 4: COMPLEXITY
    complexity_class = s2_result.get("complexity_class", "M")
    ws["C4"] = complexity_class

    # Row 5: TOTAL EFFORT
    total_weeks = s3_result.get("total_weeks", 0)
    ws["C5"] = f"{total_weeks} weeks"

    # Row 6: PROJECT END DATE
    project_end = s3_result.get("project_end_date", "")
    ws["C6"] = project_end


def _write_tracker_rows(ws, s4_result: dict, use_case_name: str):
    """
    Write sequenced WBS rows starting at row 19.
    CRITICAL: Write formulas for SP and Dev Status columns, not computed values.
    NEVER overwrite dashboard rows 8-16 or cell C16.
    """
    sequenced_rows = s4_result.get("sequenced_rows", [])

    if not sequenced_rows:
        logger.warning("No sequenced_rows in s4_result")
        return

    # Starting row for data (row 18 is header, row 19+ is data)
    start_row = 19
    developer = "Developer Name"  # TODO: get from project config or use_case

    for idx, row_data in enumerate(sequenced_rows):
        row_num = start_row + idx

        # Column B: feature name
        ws[f"B{row_num}"] = row_data.get("feature", "")

        # Column C: scope (always "ORIGINAL")
        ws[f"C{row_num}"] = "ORIGINAL"

        # Column D: acceptance_status (blank initially)
        ws[f"D{row_num}"] = ""

        # Column E: start_date
        ws[f"E{row_num}"] = row_data.get("start_date", "")

        # Column F: end_date
        ws[f"F{row_num}"] = row_data.get("end_date", "")

        # Column G: SP — FORMULA (not computed value)
        ws[f"G{row_num}"] = FORMULA_SP

        # Column H: hours
        ws[f"H{row_num}"] = row_data.get("hours", 0.0)

        # Column I: developer
        ws[f"I{row_num}"] = developer

        # Column J: priority
        ws[f"J{row_num}"] = row_data.get("priority", "MUST")

        # Column K: completion_pct (blank initially)
        ws[f"K{row_num}"] = ""

        # Column L: dev_status — FORMULA (not computed value)
        ws[f"L{row_num}"] = formula_dev_status(row_num)

        # Columns M-O: blank
        ws[f"M{row_num}"] = ""
        ws[f"N{row_num}"] = ""
        ws[f"O{row_num}"] = ""

    logger.info(f"Wrote {len(sequenced_rows)} tracker rows starting at row {start_row}")
