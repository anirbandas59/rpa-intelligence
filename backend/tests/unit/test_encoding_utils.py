"""Tests for encoding utilities."""

import tempfile
from pathlib import Path

import pytest

from core.utils.encoding import (
    detect_encoding,
    normalize_text_encoding,
    read_text_file_with_fallback,
)


class TestReadTextFileWithFallback:
    """Test read_text_file_with_fallback function."""

    def test_read_utf8_file(self):
        """Should read UTF-8 encoded file."""
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as f:
            f.write("Hello UTF-8 world! 你好")
            temp_path = Path(f.name)

        try:
            content = read_text_file_with_fallback(temp_path)
            assert content == "Hello UTF-8 world! 你好"
        finally:
            temp_path.unlink()

    def test_read_windows1252_file(self):
        """Should read Windows-1252 encoded file with curly quotes."""
        # Create file with Windows-1252 encoding (byte 0x93 = left double quote)
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            # "Hello" with Windows-1252 curly quotes
            content = b"Hello \x93world\x94"
            f.write(content)
            temp_path = Path(f.name)

        try:
            content = read_text_file_with_fallback(temp_path)
            # Should decode successfully (exact character depends on Windows-1252 mapping)
            assert "Hello" in content
            assert "world" in content
        finally:
            temp_path.unlink()

    def test_read_latin1_file(self):
        """Should read ISO-8859-1 (Latin-1) encoded file."""
        with tempfile.NamedTemporaryFile(mode="w", encoding="iso-8859-1", delete=False, suffix=".txt") as f:
            f.write("Café résumé")
            temp_path = Path(f.name)

        try:
            content = read_text_file_with_fallback(temp_path)
            assert "Café" in content
            assert "résumé" in content
        finally:
            temp_path.unlink()

    def test_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            read_text_file_with_fallback("/nonexistent/file.txt")


class TestDetectEncoding:
    """Test detect_encoding function."""

    def test_detect_utf8(self):
        """Should detect UTF-8 encoding."""
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as f:
            f.write("UTF-8 test 测试")
            temp_path = Path(f.name)

        try:
            encoding = detect_encoding(temp_path)
            assert encoding == "utf-8"
        finally:
            temp_path.unlink()

    def test_detect_windows1252(self):
        """Should detect Windows-1252 encoding."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            # Windows-1252 with curly quotes
            f.write(b"Test \x93quote\x94 text")
            temp_path = Path(f.name)

        try:
            encoding = detect_encoding(temp_path)
            # Should detect as windows-1252 or compatible encoding
            assert encoding in ["windows-1252", "cp1252", "iso-8859-1", "latin-1"]
        finally:
            temp_path.unlink()

    def test_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            detect_encoding("/nonexistent/file.txt")


class TestNormalizeTextEncoding:
    """Test normalize_text_encoding function."""

    def test_normalize_curly_quotes(self):
        """Should normalize Windows-1252 curly quotes."""
        text = "Hello \x93world\x94"
        normalized = normalize_text_encoding(text)
        assert normalized == 'Hello "world"'

    def test_normalize_single_quotes(self):
        """Should normalize single quotes."""
        text = "It\x92s a \x91test\x92"
        normalized = normalize_text_encoding(text)
        assert normalized == "It's a 'test'"

    def test_normalize_dashes(self):
        """Should normalize en-dash and em-dash."""
        text = "Range: 1\x96100, Note\x97important"
        normalized = normalize_text_encoding(text)
        assert normalized == "Range: 1–100, Note—important"

    def test_normalize_ellipsis(self):
        """Should normalize ellipsis."""
        text = "Wait\x85 what?"
        normalized = normalize_text_encoding(text)
        assert normalized == "Wait… what?"

    def test_no_changes_for_clean_text(self):
        """Should not modify clean UTF-8 text."""
        text = "Clean UTF-8 text with proper punctuation."
        normalized = normalize_text_encoding(text)
        assert normalized == text

    def test_mixed_artifacts(self):
        """Should handle multiple encoding artifacts."""
        text = "He said \x93It\x92s ready\x94\x97or is it\x85"
        normalized = normalize_text_encoding(text)
        expected = 'He said "It\'s ready"—or is it…'
        assert normalized == expected
