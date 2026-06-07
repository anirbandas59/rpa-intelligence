"""
Document agent — extracts raw text from uploaded files.
Supports .docx and .pdf formats.
Zero LLM calls.
"""

import logging
from pathlib import Path
from typing import TypedDict

import fitz  # PyMuPDF
from docx import Document

from core.exceptions import DocumentProcessingError

logger = logging.getLogger(__name__)


class DocumentState(TypedDict):
    """State for document processing."""

    file_path: str
    raw_text: str
    error: str | None


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from .docx file using python-docx.

    Args:
        file_path: Path to .docx file

    Returns:
        Extracted text content

    Raises:
        DocumentProcessingError: If file cannot be read
    """
    try:
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        raise DocumentProcessingError(f"Failed to extract text from DOCX: {e}")


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from .pdf file using PyMuPDF.

    Args:
        file_path: Path to .pdf file

    Returns:
        Extracted text content

    Raises:
        DocumentProcessingError: If file cannot be read or is encrypted
    """
    try:
        doc = fitz.open(file_path)
        if doc.is_encrypted:
            raise DocumentProcessingError(
                "PDF is encrypted. Please provide an unencrypted version."
            )

        pages = []
        for page in doc:
            text = page.get_text()
            if isinstance(text, str) and text.strip():
                pages.append(text)

        doc.close()
        return "\n\n".join(pages)
    except DocumentProcessingError:
        raise
    except Exception as e:
        raise DocumentProcessingError(f"Failed to extract text from PDF: {e}")


def process_document(file_path: str) -> str:
    """
    Process uploaded document and extract text.
    Entry point for document agent.

    Args:
        file_path: Path to uploaded file

    Returns:
        Extracted text content

    Raises:
        DocumentProcessingError: If file type unsupported or extraction fails
    """
    path = Path(file_path)

    if not path.exists():
        raise DocumentProcessingError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    logger.info(f"Processing document: {file_path} (type: {suffix})")

    if suffix == ".docx":
        text = extract_text_from_docx(file_path)
    elif suffix == ".pdf":
        text = extract_text_from_pdf(file_path)
    else:
        raise DocumentProcessingError(
            f"Unsupported file type: {suffix}. Only .docx and .pdf are supported."
        )

    if not text.strip():
        raise DocumentProcessingError("Extracted text is empty. Please check the document content.")

    logger.info(f"Successfully extracted {len(text)} characters from document")
    return text
