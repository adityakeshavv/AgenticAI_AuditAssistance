from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Agentic AI-Powered Audit Assistant API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/audit_assistant",
        description="SQLAlchemy database URL for PostgreSQL.",
    )
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "AUDIT_OPENAI_API_KEY"),
        description="API key for OpenAI-compatible LLM routing.",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("OPENAI_MODEL", "AUDIT_OPENAI_MODEL"),
        description="OpenAI-compatible model used by the LLM router.",
    )
    rag_root_dir: Path = Field(
        default=REPO_ROOT / "rag",
        validation_alias=AliasChoices("RAG_ROOT_DIR", "AUDIT_RAG_ROOT_DIR"),
        description="Root directory containing RAG documents and metadata.",
    )
    rag_documents_dir: Path = Field(
        default=REPO_ROOT / "rag" / "documents",
        validation_alias=AliasChoices("RAG_DOCUMENTS_DIR", "AUDIT_RAG_DOCUMENTS_DIR"),
        description="Directory containing raw unstructured documents.",
    )
    rag_metadata_dir: Path = Field(
        default=REPO_ROOT / "rag" / "metadata",
        validation_alias=AliasChoices("RAG_METADATA_DIR", "AUDIT_RAG_METADATA_DIR"),
        description="Directory containing document metadata CSV files.",
    )

    default_page: int = 1
    default_page_size: int = 50
    max_page_size: int = 500

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="AUDIT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
