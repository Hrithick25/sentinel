"""
SENTINEL Gateway — Configuration
===================================
Server-side config. Only loaded when running the gateway (not the SDK client).

Supports two database backends:
  1. PostgreSQL (self-hosted via Docker or bare-metal)
  2. Supabase (cloud-hosted, zero Docker needed)

Set DATABASE_BACKEND=supabase in .env to use Supabase.

SECURITY CHECKLIST (before going to production):
  ✅ SECRET_KEY — must be a cryptographically random 64+ char string
  ✅ DATABASE_URL — use strong credentials, not "sentinel:sentinel"
  ✅ CORS_ORIGINS — restrict to your domain(s)
  ✅ OPENAI_API_KEY — never commit to version control
  ✅ ENVIRONMENT=production — enables strict CORS + logging hardening
"""
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from typing import List
import json
import logging
import warnings

_cfg_logger = logging.getLogger("sentinel.config")


class Settings(BaseSettings):
    # App
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # ── Database Backend ──────────────────────────────────────────────────────
    # "postgres" = self-hosted PostgreSQL (Docker or bare-metal)
    # "supabase" = cloud-hosted Supabase (no Docker needed)
    database_backend: str = "postgres"

    # Postgres (used when database_backend = "postgres")
    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel_db"
    sync_database_url: str = "postgresql://sentinel:sentinel@localhost:5432/sentinel_db"

    # Supabase (used when database_backend = "supabase")
    supabase_url: str = ""          # e.g. https://xxxx.supabase.co
    supabase_anon_key: str = ""     # public anon key
    supabase_service_key: str = ""  # service_role key (server-side only)

    # Redis — used for policy cache, agent weights, counters
    # Set to "" to disable (graceful fallback to in-memory dict)
    # Default is DISABLED. Opt-in by setting REDIS_URL=redis://... in .env
    redis_url: str = ""
    redis_ttl: int = 30  # seconds — policy cache TTL

    # Kafka — set to "" to disable (graceful fallback to direct DB writes)
    kafka_bootstrap_servers: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # FAISS
    faiss_index_path: str = "./data/faiss_index"
    faiss_dim: int = 384

    # Models (can swap for faster/slower variants)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    multilingual_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    spacy_model: str = "en_core_web_sm"
    nli_model: str = "cross-encoder/nli-deberta-v3-small"

    # Safety defaults — overridden per-tenant from DB
    # v1 agents
    default_injection_threshold: float = 0.85
    default_pii_threshold: float = 0.70
    default_toxicity_threshold: float = 0.60
    default_hallucination_threshold: float = 0.50
    default_jailbreak_threshold: float = 0.75
    # v2 agents
    default_response_safety_threshold: float = 0.50
    default_multilingual_threshold: float = 0.65
    default_tool_call_threshold: float = 0.60
    default_brand_guard_threshold: float = 0.50
    default_token_anomaly_threshold: float = 0.60

    # CORS — set to your production domain(s) in .env
    cors_origins: str = '["http://localhost:5173","http://localhost:3000","http://localhost:8080"]'

    # Rate limiting defaults
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 10

    # Security hardening
    max_request_body_bytes: int = 1_048_576   # 1 MB
    max_prompt_chars: int = 32_768             # 32k chars

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.cors_origins)
        except json.JSONDecodeError:
            return [self.cors_origins]

    # Gateway URL — used by SDK
    gateway_url: str = "http://localhost:8000"

    @property
    def use_supabase(self) -> bool:
        return self.database_backend.lower() == "supabase"

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        if self.environment == "production":
            if self.secret_key in ("change-me-in-production", "", "secret", "dev"):
                raise ValueError(
                    "CRITICAL SECURITY: SECRET_KEY must be set to a strong random value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(64))\""
                )
            if self.database_url and "sentinel:sentinel@" in self.database_url:
                warnings.warn(
                    "WARNING: Using default database credentials in production is insecure. "
                    "Change DATABASE_URL credentials immediately.",
                    UserWarning,
                    stacklevel=2,
                )
        else:
            if self.secret_key in ("change-me-in-production", ""):
                _cfg_logger.warning(
                    "⚠️  SECRET_KEY is using the insecure default. "
                    "Set SECRET_KEY in .env before deploying to production."
                )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
