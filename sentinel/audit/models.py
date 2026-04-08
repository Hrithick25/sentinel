"""
SENTINEL Audit — SQLAlchemy Models
======================================
Tables:
  audit_events   — one row per SENTINEL decision (signed JSON attestation)
  tenant_records — tenant registry + auth
  policy_records — per-tenant safety thresholds (live-updatable)

These models are ONLY used when database_backend=postgres (self-hosted).
When database_backend=supabase, the Supabase adapter bypasses SQLAlchemy.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, func
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from sentinel.config import settings

logger = logging.getLogger("sentinel.audit.models")

# ── Engine ─────────────────────────────────────────────────────────────────────
# Only connect to Postgres when using postgres backend
if not settings.use_supabase:
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
else:
    engine = None
    AsyncSessionLocal = None
    logger.info("Supabase backend active — SQLAlchemy engine skipped")


class Base(DeclarativeBase):
    pass


# ── Dependency ─────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if settings.use_supabase or AsyncSessionLocal is None:
        # Supabase mode: yield a sentinel placeholder
        # The gateway routes that need DB will use the Supabase adapter instead
        yield None  # type: ignore
        return

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ── Table definitions ──────────────────────────────────────────────────────────

class AuditRecord(Base):
    __tablename__ = "audit_events"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    audit_id          = Column(String(36), unique=True, nullable=False, index=True)
    request_id        = Column(String(36), nullable=False, index=True)
    tenant_id         = Column(String(64), nullable=False, index=True)
    timestamp         = Column(DateTime, default=datetime.utcnow, nullable=False)
    decision          = Column(String(10), nullable=False)   # ALLOW / REWRITE / BLOCK
    aggregate_score   = Column(Float, nullable=False)
    triggering_agent  = Column(String(64), nullable=True)
    agent_scores      = Column(Text, nullable=True)          # JSON
    compliance_tags   = Column(Text, nullable=True)          # JSON array
    prompt_hash       = Column(String(64), nullable=False)   # SHA-256
    rewritten         = Column(Boolean, default=False)
    latency_ms        = Column(Float, nullable=True)
    signature         = Column(Text, nullable=True)          # HMAC attestation
    explanation       = Column(Text, nullable=True)          # v3: explainability engine output


class TenantRecord(Base):
    __tablename__ = "tenant_records"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id     = Column(String(64), unique=True, nullable=False, index=True)
    name          = Column(String(128), nullable=False)
    email         = Column(String(256), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    use_case           = Column(String(64), default="general")
    stripe_customer_id = Column(String(64), nullable=True)
    plan               = Column(String(32), default="oss_core")
    pricing_tier       = Column(String(32), default="oss_core")
    compliance_region  = Column(String(32), default="global")
    created_at    = Column(DateTime, default=datetime.utcnow)
    is_active     = Column(Boolean, default=True)


class PolicyRecord(Base):
    __tablename__ = "policy_records"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id             = Column(String(64), unique=True, nullable=False, index=True)
    use_case              = Column(String(64), default="general")
    injection_threshold       = Column(Float, default=0.85)
    pii_threshold             = Column(Float, default=0.70)
    toxicity_threshold        = Column(Float, default=0.60)
    hallucination_threshold     = Column(Float, default=0.50)
    jailbreak_threshold       = Column(Float, default=0.75)
    response_safety_threshold = Column(Float, default=0.50)
    multilingual_threshold    = Column(Float, default=0.65)
    tool_call_threshold       = Column(Float, default=0.60)
    brand_guard_threshold     = Column(Float, default=0.50)
    token_anomaly_threshold   = Column(Float, default=0.60)
    lower_threshold           = Column(Float, default=0.35)
    upper_threshold           = Column(Float, default=0.70)
    pii_action                = Column(String(16), default="redact")
    allow_rewrite             = Column(Boolean, default=True)
    compliance_region         = Column(String(16), default="global")
    dpdp_enabled              = Column(Boolean, default=False)
    rbi_framework_enabled     = Column(Boolean, default=False)
    shadow_mode               = Column(Boolean, default=False)     # v3: log without blocking
    updated_at            = Column(DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow)
