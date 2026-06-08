"""Core utility functions."""

from .encoding import read_text_file_with_fallback, detect_encoding, normalize_text_encoding

__all__ = ["read_text_file_with_fallback", "detect_encoding", "normalize_text_encoding"]
