"""Typed exception hierarchy for RPA Intelligence Platform.

All exceptions inherit from RPABaseError and support optional context dictionaries
for structured error information.
"""

from typing import Any


class RPABaseError(Exception):
    """Base exception for all project errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        """Initialize exception with message and optional context.

        Args:
            message: Human-readable error description
            context: Optional dict with additional context information
        """
        self.message = message
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        """Return formatted string representation."""
        class_name = self.__class__.__name__
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{class_name}: {self.message} ({context_str})"
        return f"{class_name}: {self.message}"


class DocumentProcessingError(RPABaseError):
    """Raised when file parsing, OCR, or extraction fails."""

    pass


class ScoringValidationError(RPABaseError):
    """Raised when scores are invalid or out of acceptable range."""

    pass


class LLMProviderError(RPABaseError):
    """Raised when LLM API calls fail (auth, timeout, etc)."""

    pass


class AgentExecutionError(RPABaseError):
    """Raised when LangGraph nodes or state transitions fail."""

    pass


class OutputGenerationError(RPABaseError):
    """Raised when Excel or PDF generation fails."""

    pass
