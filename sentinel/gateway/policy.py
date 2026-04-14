"""
SENTINEL Policy Resolver
==========================
Loads per-tenant safety policies from Postgres with a 30-second TTL
Redis cache.  Falls back to sensible defaults if no record exists.
"""
from __future__ import annotations

import logging
import json
from typing import Optional

from sentinel.config import settings
from sentinel.models import TenantPolicy
from sentinel.storage.redis_client import get_redis

logger = logging.getLogger("sentinel.policy")

_POLICY_KEY_PREFIX = "sentinel:policy:"


async def resolve_policy(tenant_id: str, db=None) -> TenantPolicy:
    """
    1. Check Redis cache (TTL = 30s)
    2. If miss → load from Postgres via SQLAlchemy
    3. Write back to Redis
    4. If still not found → return defaults

    db: AsyncSession — pass from FastAPI dependency if available.
    """
    redis = await get_redis()
    cache_key = f"{_POLICY_KEY_PREFIX}{tenant_id}"

    # ── Cache hit ──────────────────────────────────────────────────────────────
    cached = await redis.get(cache_key)
    if cached:
        try:
            return TenantPolicy(**json.loads(cached))
        except Exception as exc:
            logger.warning("Policy cache parse error: %s", exc)

    # ── Postgres lookup ────────────────────────────────────────────────────────
    policy: Optional[TenantPolicy] = None
    if db is not None:
        try:
            from sentinel.audit.models import PolicyRecord
            from sqlalchemy import select

            result = await db.execute(
                select(PolicyRecord).where(PolicyRecord.tenant_id == tenant_id)
            )
            row = result.scalar_one_or_none()
            if row:
                policy = TenantPolicy(
                    tenant_id=row.tenant_id,
                    use_case=row.use_case,
                    injection_threshold=row.injection_threshold,
                    pii_threshold=row.pii_threshold,
                    toxicity_threshold=row.toxicity_threshold,
                    hallucination_threshold=row.hallucination_threshold,
                    jailbreak_threshold=row.jailbreak_threshold,
                    response_safety_threshold=row.response_safety_threshold,
                    multilingual_threshold=row.multilingual_threshold,
                    tool_call_threshold=row.tool_call_threshold,
                    brand_guard_threshold=row.brand_guard_threshold,
                    token_anomaly_threshold=row.token_anomaly_threshold,
                    lower_threshold=row.lower_threshold,
                    upper_threshold=row.upper_threshold,
                    pii_action=row.pii_action,
                    allow_rewrite=row.allow_rewrite,
                    compliance_region=row.compliance_region,
                    dpdp_enabled=row.dpdp_enabled,
                    rbi_framework_enabled=row.rbi_framework_enabled,
                    shadow_mode=row.shadow_mode if hasattr(row, 'shadow_mode') else False,
                    updated_at=row.updated_at,
                )
        except Exception as exc:
            logger.error("Policy DB lookup failed: %s", exc)

    # ── Default fallback ───────────────────────────────────────────────────────
    if policy is None:
        policy = TenantPolicy(
            tenant_id=tenant_id,
            injection_threshold=settings.default_injection_threshold,
            pii_threshold=settings.default_pii_threshold,
            toxicity_threshold=settings.default_toxicity_threshold,
            hallucination_threshold=settings.default_hallucination_threshold,
            jailbreak_threshold=settings.default_jailbreak_threshold,
            response_safety_threshold=settings.default_response_safety_threshold,
            multilingual_threshold=settings.default_multilingual_threshold,
            tool_call_threshold=settings.default_tool_call_threshold,
            brand_guard_threshold=settings.default_brand_guard_threshold,
            token_anomaly_threshold=settings.default_token_anomaly_threshold,
        )
        logger.info("Using default policy for tenant=%s", tenant_id)

    # ── Write cache ────────────────────────────────────────────────────────────
    await redis.set(
        cache_key,
        policy.model_dump_json(),
        ex=settings.redis_ttl,
    )

    return policy


async def invalidate_policy_cache(tenant_id: str) -> None:
    """Call after PUT /admin/policy to force immediate policy refresh."""
    redis = await get_redis()
    await redis.delete(f"{_POLICY_KEY_PREFIX}{tenant_id}")
    logger.info("Policy cache invalidated for tenant=%s", tenant_id)
