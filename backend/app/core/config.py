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
    agent_runtime: str = Field(
        default="legacy",
        validation_alias=AliasChoices("AGENT_RUNTIME", "AUDIT_AGENT_RUNTIME"),
        description="Workflow runtime to use. Set to gemini_adk to enable the ADK adapter path.",
    )
    google_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY", "AUDIT_GOOGLE_API_KEY"),
        description="Google API key for Gemini-based agent workflows when applicable.",
    )
    google_cloud_project_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT_ID", "AUDIT_GOOGLE_CLOUD_PROJECT_ID"),
        description="Google Cloud project for Gemini ADK / Vertex AI workflows.",
    )
    google_cloud_location: str = Field(
        default="us-central1",
        validation_alias=AliasChoices("GOOGLE_CLOUD_LOCATION", "AUDIT_GOOGLE_CLOUD_LOCATION"),
        description="Google Cloud region for Gemini ADK / Vertex AI workflows.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-pro",
        validation_alias=AliasChoices("GEMINI_MODEL", "AUDIT_GEMINI_MODEL"),
        description="Gemini model used by the ADK adapter path.",
    )
    langfuse_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("LANGFUSE_ENABLED", "AUDIT_LANGFUSE_ENABLED"),
        description="Enable Langfuse tracing when credentials are available.",
    )
    langfuse_public_key: str = Field(
        default="",
        validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY", "AUDIT_LANGFUSE_PUBLIC_KEY"),
        description="Public key for Langfuse tracing.",
    )
    langfuse_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("LANGFUSE_SECRET_KEY", "AUDIT_LANGFUSE_SECRET_KEY"),
        description="Secret key for Langfuse tracing.",
    )
    langfuse_host: str = Field(
        default="",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL", "AUDIT_LANGFUSE_HOST", "AUDIT_LANGFUSE_BASE_URL"),
        description="Langfuse host URL.",
    )
    langfuse_trace_url_template: str = Field(
        default="",
        validation_alias=AliasChoices("LANGFUSE_TRACE_URL_TEMPLATE", "AUDIT_LANGFUSE_TRACE_URL_TEMPLATE"),
        description="Optional template for direct Langfuse trace links. Use {trace_id} as a placeholder.",
    )
    database_connection_encryption_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "DATABASE_CONNECTION_ENCRYPTION_KEY",
            "AUDIT_DATABASE_CONNECTION_ENCRYPTION_KEY",
        ),
        description="Optional Fernet key used to encrypt saved database connection passwords.",
    )
    auth_token_secret: str = Field(
        default="change-me-in-env",
        validation_alias=AliasChoices("AUTH_TOKEN_SECRET", "AUDIT_AUTH_TOKEN_SECRET"),
        description="Secret used to sign application auth tokens and OAuth state.",
    )
    auth_token_expiry_minutes: int = Field(
        default=12 * 60,
        validation_alias=AliasChoices("AUTH_TOKEN_EXPIRY_MINUTES", "AUDIT_AUTH_TOKEN_EXPIRY_MINUTES"),
        description="Lifetime for signed application auth tokens.",
    )
    admin_email_allowlist: str = Field(
        default="",
        validation_alias=AliasChoices("ADMIN_EMAILS", "AUDIT_ADMIN_EMAILS"),
        description="Comma-separated list of email addresses that should receive admin access.",
    )
    google_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_CLIENT_ID", "AUDIT_GOOGLE_CLIENT_ID"),
        description="Google OAuth client ID for Google sign-in.",
    )
    google_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_CLIENT_SECRET", "AUDIT_GOOGLE_CLIENT_SECRET"),
        description="Google OAuth client secret for Google sign-in.",
    )
    google_redirect_uri: str = Field(
        default="http://localhost:8000/auth/google/callback",
        validation_alias=AliasChoices("GOOGLE_REDIRECT_URI", "AUDIT_GOOGLE_REDIRECT_URI"),
        description="Backend callback URI configured in Google OAuth console.",
    )
    frontend_auth_redirect_uri: str = Field(
        default="http://localhost:5173/",
        validation_alias=AliasChoices("FRONTEND_AUTH_REDIRECT_URI", "AUDIT_FRONTEND_AUTH_REDIRECT_URI"),
        description="Frontend URL used after completing Google sign-in.",
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
    document_uploads_dir: Path = Field(
        default=REPO_ROOT / "rag" / "documents" / "uploads",
        validation_alias=AliasChoices("DOCUMENT_UPLOADS_DIR", "AUDIT_DOCUMENT_UPLOADS_DIR"),
        description="Directory used to store user-uploaded documents.",
    )
    rag_metadata_dir: Path = Field(
        default=REPO_ROOT / "rag" / "metadata",
        validation_alias=AliasChoices("RAG_METADATA_DIR", "AUDIT_RAG_METADATA_DIR"),
        description="Directory containing document metadata CSV files.",
    )
    document_source_uri_scheme: str = Field(
        default="file",
        validation_alias=AliasChoices("DOCUMENT_SOURCE_URI_SCHEME", "AUDIT_DOCUMENT_SOURCE_URI_SCHEME"),
        description="URI scheme used when building document source links.",
    )
    document_source_uri_base: str = Field(
        default="",
        validation_alias=AliasChoices("DOCUMENT_SOURCE_URI_BASE", "AUDIT_DOCUMENT_SOURCE_URI_BASE"),
        description="Optional base URI used when building document source links.",
    )

    default_page: int = 1
    default_page_size: int = 50
    max_page_size: int = 500

    finding_high_flagged_transaction_threshold: int = 5
    finding_supporting_audit_document_bonus: bool = True
    finding_supporting_investigation_document_bonus: bool = True
    finding_no_evidence_risk: str = "LOW"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="AUDIT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
