from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # API keys and endpoints
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    default_primary_model: str = Field(default="gpt-4o-mini")
    default_fallback_models: list[str] = Field(default_factory=lambda: ["gpt-3.5-turbo"])  # noqa: B008

    # Redis / Qdrant
    redis_url: str = Field(default="redis://localhost:6379/0")
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str = Field(default="")
    cache_ttl_seconds: int = Field(default=3600)

    # Observability
    langfuse_public_key: str = Field(default="", env="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", env="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")
    log_path: str = Field(default="data/interactions.jsonl")

    # Presidio configuration
    presidio_analyzer_url: str = Field(default="")
    presidio_anonymizer_url: str = Field(default="")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
