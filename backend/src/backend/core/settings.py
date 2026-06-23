"""Application settings loaded from environment variables.

All secrets (AWS credentials, Cognito IDs) come from env or AWS SSM.
Nothing sensitive is hardcoded.  See backend/.env.example for the full
list of supported variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic-settings model for the FastAPI backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    app_env: str = Field(default="development", description="Deployment environment label.")
    log_level: str = Field(default="INFO", description="Root logging level.")
    runtime_mode: str = Field(
        default="local",
        description="'local' runs LangGraph in-process; 'agentcore' delegates to AgentCore Runtime.",
    )

    # ── AWS ────────────────────────────────────────────────────────────────
    aws_region: str = Field(default="us-east-1")
    aws_profile: str | None = Field(default=None, description="Named AWS CLI profile (leave blank for IAM role).")

    # ── S3 ─────────────────────────────────────────────────────────────────
    s3_bucket_name: str = Field(default="loan-origination-documents-demo")
    s3_endpoint_url: str | None = Field(
        default=None,
        description="Override S3 endpoint for local mocking (e.g. LocalStack).",
    )

    # ── Amazon Cognito ─────────────────────────────────────────────────────
    cognito_region: str = Field(default="us-east-1")
    cognito_user_pool_id: str = Field(default="")
    cognito_client_id: str = Field(default="")
    cognito_jwks_uri: str | None = Field(
        default=None,
        description="Override JWKS URI for local mocking only; derived automatically in production.",
    )

    # ── AgentCore ──────────────────────────────────────────────────────────
    agentcore_runtime_arn: str = Field(default="")
    agentcore_gateway_arn: str = Field(default="")

    # ── Operational knobs ──────────────────────────────────────────────────
    presigned_url_ttl_seconds: int = Field(default=900, description="TTL for S3 presigned PUT URLs.")
    runtime_timeout_seconds: int = Field(default=30, description="Network timeout for Runtime API calls.")
    runtime_max_retries: int = Field(default=3, description="Max retries for transient Runtime failures.")

    @property
    def jwks_uri(self) -> str:
        """JWKS endpoint derived from the Cognito pool ID unless explicitly overridden."""
        if self.cognito_jwks_uri:
            return self.cognito_jwks_uri
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}/.well-known/jwks.json"
        )

    @property
    def cognito_issuer(self) -> str:
        """Expected `iss` claim value for JWTs from this user pool."""
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}"
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

from functools import lru_cache  # noqa: E402


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance (loaded once from environment)."""
    return Settings()
