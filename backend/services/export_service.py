"""
Excel export service for Stage 4 sprint tracker generation.

Generates Excel workbook from output_template.xlsx with three sheets: Dashboard,
Tracker (Feature and delivery timeline), and Project Details. Fills WBS rows with
data from Stage 4 while preserving template formulas for calculated columns.

Key responsibilities:
- Load output_template.xlsx with formulas intact (data_only=False)
- Write project metadata to Dashboard sheet (name, complexity, effort, end date)
- Write tracker rows to Tracker sheet starting at row 19
- Preserve Excel formulas for SP column (=ROUND($C$16*Hours,2))
- Preserve Excel formulas for Dev Status column (VLOOKUP against Dashboard lookup table)
- Never overwrite Dashboard rows 8-16 (lookup table) or cell C16 (SP constant)

CRITICAL constraints:
- SP column: ALWAYS write formula =ROUND($C$16*Hours,2), NEVER Python-calculated value
- Dev Status column: ALWAYS write VLOOKUP formula, NEVER Python-calculated value
- Dashboard rows 8-16: NEVER modify (contains status lookup table)
- Cell C16: NEVER modify (contains SP conversion constant 0.0666)

Uses openpyxl for Excel manipulation and export_tool for formula generation.
"""

import io
import logging
from pathlib import Path

import openpyxl

from tools.output.export_tool import FORMULA_SP, formula_dev_status

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "templates" / "output_template.xlsx"


def generate_tracker_xlsx(
    use_case_name: str, s2_result: dict, s3_result: dict, s4_result: dict
) -> io.BytesIO:
    """
    Generate Excel tracker workbook from output_template.xlsx with formula preservation.

    Loads template with data_only=False to preserve formulas, writes project metadata
    and WBS rows, then returns in-memory buffer for download. SP and Dev Status columns
    are written as formulas (not values) per CLAUDE.md constraints.

    Args:
        use_case_name: Project/use case name for display
        s2_result: Stage 2 complexity result dict (complexity_class)
        s3_result: Stage 3 timeline result dict (total_weeks, project_end_date, phases)
        s4_result: Stage 4 tracker result dict (sequenced_rows with feature, hours, start_date, etc.)

    Returns:
        BytesIO buffer containing Excel workbook ready for download

    Flow:
    1. Load output_template.xlsx with formulas intact
    2. Write metadata to rows 3-6 (name, complexity, effort, end date)
    3. Write tracker rows starting at row 19 (formulas for SP and Dev Status)
    4. Save to BytesIO buffer and return
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

    logger.info("Generated tracker xlsx with sequenced rows")
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
