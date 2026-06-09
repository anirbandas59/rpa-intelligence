"""Core utility functions."""

from .encoding import detect_encoding, normalize_text_encoding, read_text_file_with_fallback

__all__ = ["read_text_file_with_fallback", "detect_encoding", "normalize_text_encoding"]
