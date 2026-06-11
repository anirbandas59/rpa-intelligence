"""
Configuration management for RPA Intelligence Platform using Pydantic Settings.

Provides type-safe configuration loading from environment variables and .env file
with validation. All settings are loaded via Settings class which extends BaseSettings.
Singleton pattern via @lru_cache ensures configuration is loaded once and reused.

Key features:
- Environment variable loading with .env fallback
- Type validation and conversion (str, int, bool, Literal)
- Model validators for production guards and provider key validation
- Case-insensitive environment variable names
- Field descriptions for IDE hints and documentation
- LRU cache for singleton behavior

Configuration groups:
- LLM: Provider selection, model names, API keys (Anthropic, OpenAI, WatsonX, Ollama)
- Database: Connection URL (SQLite dev, PostgreSQL prod)
- Security: JWT secret, token expiry, API secret key
- Paths: Output directory, temp directory, log level
- Deployment: Environment (dev/prod), frontend URL, CORS
- Agent: Feature flags for LangGraph vs legacy pipelines
- Redis: Session storage URL

Usage:
    from config.settings import get_settings
    settings = get_settings()
    llm_model = settings.default_llm_model
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    default_llm_provider: str = Field(
        default="anthropic",
        description="LLM provider: anthropic | openai | watsonx | ollama",
    )
    default_llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Model name for the chosen provider",
    )

    # Stage-Specific LLM Models (per CLAUDE.md AI Model Assignments)
    stage1_llm_model: str = Field(
        default="claude-haiku-4-5",
        description="Stage 1 (Migration Assessment): Haiku for parallel per-use-case scoring",
    )
    stage2_extraction_llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Stage 2 (Band Extraction): Sonnet for accurate complexity band extraction",
    )
    stage2_scoring_llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Stage 2 (Complexity Scoring): Sonnet for LangGraph complexity assessment",
    )
    stage3_task_extraction_llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Stage 3 (Task Extraction): Sonnet for task decomposition with hour validation",
    )
    stage3_task_synthesis_llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Stage 3 (Task Synthesis): Sonnet for synthesizing tasks without document",
    )
    stage3_narrative_llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Stage 3 (Narrative Summary): Sonnet for executive timeline narrative",
    )
    stage4_tracker_llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Stage 4 (Sprint Tracker): Sonnet for WBS grouping and sprint assignment",
    )

    # Provider API Keys
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key",
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key",
    )

    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./dev.db",
        description="Database connection URL",
    )

    # Security & Authentication
    secret_key: str = Field(
        default="",
        description="JWT secret key for token signing",
    )
    access_token_expire_minutes: int = Field(
        default=1440,
        description="JWT token expiration time in minutes (default: 24 hours)",
    )

    # Watsonx Configuration (optional)
    watsonx_api_key: str = Field(
        default="",
        description="Watsonx API key",
    )
    watsonx_url: str = Field(
        default="",
        description="Watsonx API URL",
    )
    watsonx_project_id: str = Field(
        default="",
        description="Watsonx project ID",
    )

    # Ollama Configuration (optional)
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL for local LLM",
    )

    # Application Paths
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    output_dir: str = Field(
        default="data/outputs",
        description="Output directory for generated files",
    )
    temp_dir: str = Field(
        default="data/temp",
        description="Temporary directory for processing",
    )

    # Deployment environment
    environment: Literal["development", "production"] = Field(
        default="development",
        description="Deployment environment: development | production",
    )

    # API Security
    frontend_url: str = Field(
        default="http://localhost:8501",
        description="Frontend URL allowed by CORS",
    )
    api_secret_key: str = Field(
        default="",
        description="X-API-Key value required on protected endpoints; empty disables auth",
    )

    # Session Store
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for session storage",
    )

    # LangSmith Tracing
    langsmith_api_key: str | None = Field(
        default=None,
        description="LangSmith API key for LLM call tracing (optional)",
    )

    # LLM Manager Behaviour
    llm_max_retries: int = Field(
        default=3,
        description="Max retry attempts on rate limit errors",
    )
    llm_retry_base_delay: float = Field(
        default=1.0,
        description="Base delay in seconds for exponential backoff",
    )

    # Agent Architecture
    use_langgraph_complexity_agent: bool = Field(
        default=False,
        description=(
            "Use LangGraph StateGraph agent for Stage 2 complexity assessment "
            "(default: False for legacy pipeline)"
        ),
    )

    # Task Decomposition Validation
    hour_tolerance_percentage: float = Field(
        default=30.0,
        description=(
            "Hour sum tolerance percentage for task decomposition validation. "
            "Default: 30% allows ±30% variance from target effort_hours. "
            "Example: For 200h budget, tolerance = ±60h (acceptable: 140-260h)"
        ),
    )

    @model_validator(mode="after")
    def validate_production_guards(self) -> "Settings":
        """
        Enforce security requirements for production deployments.

        Validates that critical security settings (API secret key) are configured
        when running in production mode. Prevents accidental deployment with
        development defaults.

        Returns:
            Self for method chaining

        Raises:
            ValueError: If production guards fail (e.g., missing API_SECRET_KEY in production)
        """
        if self.environment == "production" and not self.api_secret_key:
            raise ValueError("API_SECRET_KEY must be set when ENVIRONMENT=production")
        return self

    @model_validator(mode="after")
    def validate_provider_keys(self) -> "Settings":
        """
        Validate that required API keys are set for the selected LLM provider.

        Checks that the chosen default_llm_provider has corresponding API credentials.
        Skips validation in development mode to allow testing endpoints without LLM access.

        Returns:
            Self for method chaining

        Raises:
            ValueError: If provider-specific API key is missing in production mode

        Validation rules:
        - anthropic: Requires ANTHROPIC_API_KEY
        - openai: Requires OPENAI_API_KEY
        - watsonx: Requires WATSONX_API_KEY and WATSONX_URL
        - ollama: No key required (local)
        """
        # Skip LLM key validation in development mode
        if self.environment == "development":
            return self

        provider = self.default_llm_provider.lower()

        if provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when DEFAULT_LLM_PROVIDER=anthropic")

        if provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when DEFAULT_LLM_PROVIDER=openai")

        if provider == "watsonx" and not self.watsonx_api_key:
            raise ValueError(
                "WATSONX_API_KEY and WATSONX_URL required when DEFAULT_LLM_PROVIDER=watsonx"
            )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load and cache settings. Returns same instance on subsequent calls.

    Returns:
        Settings: Singleton instance of application settings.
    """
    return Settings()
