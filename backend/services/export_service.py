"""
Export service — generate Excel tracker from Stage 4 results.
3-sheet workbook: Calculator, Steps, Timeline.
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import date, timedelta
import io
import logging

logger = logging.getLogger(__name__)


def generate_tracker_xlsx(
    use_case_name: str,
    s2_result: dict,
    s3_result: dict,
    s4_result: dict
) -> io.BytesIO:
    """
    Generate 3-sheet Excel tracker from stage results.

    Args:
        use_case_name: Name of the use case
        s2_result: Stage 2 complexity result
        s3_result: Stage 3 timeline result
        s4_result: Stage 4 sprint tracker result

    Returns:
        BytesIO buffer with Excel file content
    """
    logger.info(f"Generating tracker xlsx for '{use_case_name}'")

    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet

    # Sheet 1: Calculator (complexity data)
    _create_calculator_sheet(wb, use_case_name, s2_result)

    # Sheet 2: Steps (feature list with sprint assignments)
    _create_steps_sheet(wb, use_case_name, s4_result)

    # Sheet 3: Timeline (Gantt-style)
    _create_timeline_sheet(wb, use_case_name, s3_result, s4_result)

    # Save to buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    logger.info(f"Generated tracker xlsx with {len(wb.sheetnames)} sheets")
    return buffer


def _create_calculator_sheet(wb: Workbook, use_case_name: str, s2_result: dict):
    """Sheet 1: Complexity calculator data."""
    ws = wb.create_sheet("Calculator", 0)

    # Header styling
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    # Title
    ws["A1"] = "RPA Complexity Assessment"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:D1")

    ws["A2"] = f"Process: {use_case_name}"
    ws["A2"].font = Font(italic=True)
    ws.merge_cells("A2:D2")

    # Attribute bands
    ws["A4"] = "Attribute"
    ws["B4"] = "Band"
    ws["C4"] = "Weight"
    ws["D4"] = "Source"

    for col in ["A4", "B4", "C4", "D4"]:
        ws[col].fill = header_fill
        ws[col].font = header_font
        ws[col].border = border

    attributes = [
        ("Activities", s2_result.get("bands", {}).get("activities", "M")),
        ("Business Rules", s2_result.get("bands", {}).get("business_rules", "M")),
        ("Layouts", s2_result.get("bands", {}).get("layouts", "S")),
        ("Interfaces", s2_result.get("bands", {}).get("interfaces", "S")),
        ("Technology", s2_result.get("bands", {}).get("technology", "S"))
    ]

    weights = s2_result.get("attribute_weights", {})

    row = 5
    for attr_name, band in attributes:
        ws[f"A{row}"] = attr_name
        ws[f"B{row}"] = band
        ws[f"C{row}"] = weights.get(attr_name.lower().replace(" ", "_"), 0)
        ws[f"D{row}"] = "AI Extracted"
        for col in ["A", "B", "C", "D"]:
            ws[f"{col}{row}"].border = border
        row += 1

    # Summary
    ws[f"A{row+1}"] = "Total Score"
    ws[f"B{row+1}"] = s2_result.get("total_score", 0)
    ws[f"A{row+1}"].font = Font(bold=True)
    ws[f"B{row+1}"].font = Font(bold=True)

    ws[f"A{row+2}"] = "Complexity Class"
    ws[f"B{row+2}"] = s2_result.get("complexity_class", "M")
    ws[f"A{row+2}"].font = Font(bold=True)
    ws[f"B{row+2}"].font = Font(bold=True)

    ws[f"A{row+3}"] = "Effort Estimate"
    effort_min = s2_result.get("effort_min_weeks", 0)
    effort_max = s2_result.get("effort_max_weeks", 0)
    ws[f"B{row+3}"] = f"{effort_min}-{effort_max} weeks" if effort_min != effort_max else f"{effort_min} weeks"
    ws[f"A{row+3}"].font = Font(bold=True)
    ws[f"B{row+3}"].font = Font(bold=True)

    # Column widths
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 15


def _create_steps_sheet(wb: Workbook, use_case_name: str, s4_result: dict):
    """Sheet 2: Feature list with sprint assignments."""
    ws = wb.create_sheet("Steps", 1)

    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    # Title
    ws["A1"] = "Feature & Sprint Tracker"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:F1")

    ws["A2"] = f"Process: {use_case_name}"
    ws["A2"].font = Font(italic=True)
    ws.merge_cells("A2:F2")

    # Headers
    headers = ["#", "Feature", "Description", "Size", "Points", "Sprint"]
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border

    # Feature data
    sprint_assignment = s4_result.get("sprint_assignment", {})
    sprint_plans = sprint_assignment.get("sprint_plans", [])

    row = 5
    for idx, plan in enumerate(sprint_plans, start=1):
        feature = plan["feature"]
        ws[f"A{row}"] = idx
        ws[f"B{row}"] = feature["name"]
        ws[f"C{row}"] = feature["description"]
        ws[f"D{row}"] = feature["size"]
        ws[f"E{row}"] = {"XS": 1, "S": 2, "M": 3, "L": 5, "XL": 8}[feature["size"]]
        ws[f"F{row}"] = plan["sprint_number"]

        for col in ["A", "B", "C", "D", "E", "F"]:
            ws[f"{col}{row}"].border = border

        row += 1

    # Sprint summaries
    row += 2
    ws[f"A{row}"] = "Sprint Summary"
    ws[f"A{row}"].font = Font(bold=True, size=12)
    ws.merge_cells(f"A{row}:D{row}")

    row += 1
    for col, header in zip(["A", "B", "C", "D"], ["Sprint", "Features", "Points", "Utilization"]):
        cell = ws.cell(row=row, column=ord(col) - ord("A") + 1, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border

    row += 1
    for summary in sprint_assignment.get("sprint_summaries", []):
        ws[f"A{row}"] = f"Sprint {summary['sprint_number']}"
        ws[f"B{row}"] = len(summary['features'])
        ws[f"C{row}"] = summary['total_points']
        ws[f"D{row}"] = f"{summary['utilization']}%"

        for col in ["A", "B", "C", "D"]:
            ws[f"{col}{row}"].border = border

        row += 1

    # Column widths
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 50
    ws.column_dimensions["D"].width = 8
    ws.column_dimensions["E"].width = 10
    ws.column_dimensions["F"].width = 10


def _create_timeline_sheet(wb: Workbook, use_case_name: str, s3_result: dict, s4_result: dict):
    """Sheet 3: Timeline Gantt view."""
    ws = wb.create_sheet("Timeline", 2)

    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    # Title
    ws["A1"] = "Delivery Timeline"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:E1")

    ws["A2"] = f"Process: {use_case_name}"
    ws["A2"].font = Font(italic=True)
    ws.merge_cells("A2:E2")

    # Phase headers
    headers = ["Phase", "Start Date", "End Date", "Weeks", "Status"]
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border

    # Phase data
    phases = s3_result.get("phases", [])
    row = 5
    for phase in phases:
        ws[f"A{row}"] = phase["name"]
        ws[f"B{row}"] = phase["start_date"]
        ws[f"C{row}"] = phase["end_date"]
        ws[f"D{row}"] = phase["weeks"]
        ws[f"E{row}"] = "Adjusted" if phase.get("is_delta") else "Planned"

        for col in ["A", "B", "C", "D", "E"]:
            ws[f"{col}{row}"].border = border

        row += 1

    # Summary
    row += 1
    ws[f"A{row}"] = "Total Duration"
    ws[f"B{row}"] = f"{s3_result.get('total_weeks', 0)} weeks"
    ws[f"A{row}"].font = Font(bold=True)
    ws[f"B{row}"].font = Font(bold=True)

    ws[f"A{row+1}"] = "Project End"
    ws[f"B{row+1}"] = s3_result.get("project_end_date", "")
    ws[f"A{row+1}"].font = Font(bold=True)
    ws[f"B{row+1}"].font = Font(bold=True)

    # Sprint breakdown
    row += 3
    ws[f"A{row}"] = "Sprint Breakdown"
    ws[f"A{row}"].font = Font(bold=True, size=12)
    ws.merge_cells(f"A{row}:C{row}")

    row += 1
    for col, header in zip(["A", "B", "C"], ["Sprint", "Features", "Points"]):
        cell = ws.cell(row=row, column=ord(col) - ord("A") + 1, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border

    row += 1
    sprint_summaries = s4_result.get("sprint_assignment", {}).get("sprint_summaries", [])
    for summary in sprint_summaries:
        ws[f"A{row}"] = f"Sprint {summary['sprint_number']}"
        ws[f"B{row}"] = len(summary['features'])
        ws[f"C{row}"] = summary['total_points']

        for col in ["A", "B", "C"]:
            ws[f"{col}{row}"].border = border

        row += 1

    # Column widths
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 12
