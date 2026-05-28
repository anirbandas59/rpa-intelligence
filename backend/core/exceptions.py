class RPABaseError(Exception):
    """Base for all platform exceptions."""


class DocumentProcessingError(RPABaseError):
    pass


class ScoringValidationError(RPABaseError):
    pass


class LLMProviderError(RPABaseError):
    pass


class AgentExecutionError(RPABaseError):
    pass


class OutputGenerationError(RPABaseError):
    pass
