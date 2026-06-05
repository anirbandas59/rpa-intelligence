"""Excel formula enforcement tool."""

# SP formula - always uses cell reference to C16 (the SP conversion constant)
FORMULA_SP = "=ROUND($C$16*Table5[[#This Row],[Hours]],2)"


def formula_dev_status(row_num: int) -> str:
    """Generate VLOOKUP formula for dev status column with row-specific refs."""
    k_col = f"K{row_num}"  # Completion % column
    d_col = f"D{row_num}"  # Acceptance status column
    return (
        f'=IF(AND(LEN({k_col})>0,{d_col}="APPROVED"),'
        f'VLOOKUP(Table5[[#This Row],[COMPLETION %]],COMPL_STATUS,2,1),"")'
    )


# Column mapping for Table5 (rows 19+):
# B: feature (str)
# C: scope — always "ORIGINAL"
# D: acceptance_status — blank initially
# E: start_date (date)
# F: end_date (date)
# G: SP — FORMULA_SP string
# H: hours (float)
# I: developer (str from project config or use_case)
# J: priority ("MUST" or "SHOULD")
# K: completion_pct — blank initially
# L: dev_status — FORMULA_DEV_STATUS string
# M-O: blank

# Rows 8-16: Dashboard (NEVER touch)
# Cell C16: SP conversion constant 0.0666 (NEVER overwrite)
