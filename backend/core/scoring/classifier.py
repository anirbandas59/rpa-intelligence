from core.models.scoring import ComplexityClass
from core.exceptions import ScoringValidationError

# XS is a special case handled before numeric classification
_BANDS: list[tuple[ComplexityClass, int, int]] = [
    ("S",  7,  8),
    ("M",  9,  15),
    ("L",  16, 22),
    ("XL", 23, 28),
]


def classify(total_score: int, is_xs_special_case: bool = False) -> ComplexityClass:
    """Map total weight score to complexity class.

    XS special case: max 2 attributes selected, all in XS column.
    Caller is responsible for detecting and passing is_xs_special_case=True.
    """
    if is_xs_special_case:
        return "XS"
    for cls, lo, hi in _BANDS:
        if lo <= total_score <= hi:
            return cls
    raise ScoringValidationError(
        f"Score {total_score} does not map to any complexity class. "
        f"Valid range: 7–28 (or XS special case)."
    )
