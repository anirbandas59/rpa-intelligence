import json
from pathlib import Path
from core.exceptions import ScoringValidationError


_MATRIX_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "weight_matrix.json"
_MATRIX_CACHE: dict | None = None


def load_weight_matrix() -> dict:
    """Load raw weight matrix from JSON. Returns nested dict keyed by attribute → band → weight int."""
    global _MATRIX_CACHE
    if _MATRIX_CACHE is None:
        with open(_MATRIX_PATH) as f:
            data = json.load(f)
        # Flatten: {"activities": {"XS": 2, "S": 2, ...}, ...}
        _MATRIX_CACHE = {attr: {band: values["weight"] for band, values in bands.items()} for attr, bands in data["weights"].items()}
    return _MATRIX_CACHE


def get_weight(matrix: dict, attribute: str, band: str) -> int:
    attr_weights = matrix.get(attribute)
    if attr_weights is None:
        raise ScoringValidationError(f"Unknown attribute: {attribute}")
    weight = attr_weights.get(band)
    if weight is None:
        raise ScoringValidationError(f"Unknown band '{band}' for attribute '{attribute}'")
    return weight
