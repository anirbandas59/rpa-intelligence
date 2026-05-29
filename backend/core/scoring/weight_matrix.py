import json
from pathlib import Path
from core.exceptions import ScoringValidationError


_MATRIX_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "weight_matrix.json"


def load_weight_matrix() -> dict:
    """Load raw weight matrix from JSON. Returns nested dict keyed by attribute → band → weight int."""
    with open(_MATRIX_PATH) as f:
        data = json.load(f)
    # Flatten: {"activities": {"XS": 2, "S": 2, ...}, ...}
    return {attr: {band: values["weight"] for band, values in bands.items()} for attr, bands in data["weights"].items()}


def get_weight(matrix: dict, attribute: str, band: str) -> int:
    attr_weights = matrix.get(attribute)
    if attr_weights is None:
        raise ScoringValidationError(f"Unknown attribute: {attribute}")
    weight = attr_weights.get(band)
    if weight is None:
        raise ScoringValidationError(f"Unknown band '{band}' for attribute '{attribute}'")
    return weight
