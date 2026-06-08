"""
Encoding detection and handling utilities.

Handles files with various encodings (UTF-8, Windows-1252, ISO-8859-1, etc.)
without requiring external dependencies like chardet.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Common encodings to try, in order of preference
COMMON_ENCODINGS = [
    "utf-8",
    "utf-8-sig",  # UTF-8 with BOM
    "windows-1252",  # Common in Windows documents (curly quotes, em dashes)
    "iso-8859-1",  # Latin-1
    "cp1252",  # Windows Western European
    "latin-1",  # Alias for ISO-8859-1
]


def read_text_file_with_fallback(file_path: str | Path, encodings: list[str] | None = None) -> str:
    """
    Read a text file, trying multiple encodings until one succeeds.

    Args:
        file_path: Path to the file to read
        encodings: List of encodings to try (default: COMMON_ENCODINGS)

    Returns:
        File content as string

    Raises:
        UnicodeDecodeError: If all encoding attempts fail
        FileNotFoundError: If file doesn't exist
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if encodings is None:
        encodings = COMMON_ENCODINGS

    last_error = None
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()

            # Log if non-UTF-8 encoding was used
            if encoding != "utf-8":
                logger.warning(
                    f"File {file_path.name} decoded with {encoding} encoding "
                    f"(not UTF-8). Consider re-saving as UTF-8."
                )

            return content

        except UnicodeDecodeError as e:
            last_error = e
            logger.debug(f"Failed to decode {file_path.name} with {encoding}: {e}")
            continue

        except Exception as e:
            # Unexpected error, don't try more encodings
            raise

    # All encodings failed
    raise UnicodeDecodeError(
        "multi-encoding",
        b"",
        0,
        0,
        f"Failed to decode {file_path.name} with any of: {', '.join(encodings)}. "
        f"Last error: {last_error}"
    )


def detect_encoding(file_path: str | Path, sample_size: int = 10000) -> str:
    """
    Attempt to detect file encoding by trying to decode a sample.

    Args:
        file_path: Path to the file
        sample_size: Number of bytes to read for detection

    Returns:
        Detected encoding name (one of COMMON_ENCODINGS)

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read a sample of bytes
    with open(file_path, "rb") as f:
        sample = f.read(sample_size)

    # Try each encoding
    for encoding in COMMON_ENCODINGS:
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    # Default to utf-8 if detection fails
    logger.warning(f"Could not detect encoding for {file_path.name}, defaulting to utf-8")
    return "utf-8"


def normalize_text_encoding(text: str) -> str:
    """
    Normalize text that may contain Windows-1252 or other legacy encoding artifacts.

    Replaces common problematic characters with their UTF-8 equivalents.

    Args:
        text: Input text that may contain encoding artifacts

    Returns:
        Normalized text
    """
    # Common Windows-1252 to UTF-8 replacements
    replacements = {
        '\x93': '"',  # Left double quote
        '\x94': '"',  # Right double quote
        '\x91': "'",  # Left single quote
        '\x92': "'",  # Right single quote
        '\x96': '–',  # En dash
        '\x97': '—',  # Em dash
        '\x85': '…',  # Ellipsis
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text
