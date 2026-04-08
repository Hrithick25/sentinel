"""
SENTINEL Storage — Redis Client
=================================
Singleton async Redis client used for:
  - Policy cache (30-second TTL)
  - Agent weight store (Bayesian feedback loop)
  - Realtime dashboard counters

Gracefully falls back to in-memory dict if Redis is unavailable.
This allows the gateway to run without Docker for development.
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger("sentinel.redis")

_redis_pool = None
_fallback_mode = False

# ── In-memory fallback store ───────────────────────────────────────────────────
_memory_store: Dict[str, Any] = {}
_memory_hash: Dict[str, Dict[str, str]] = {}
_memory_ttl: Dict[str, float] = {}


class _MemoryRedis:
    """Minimal in-memory Redis replacement for zero-infra dev mode."""

    async def ping(self):
        return True

    async def get(self, key: str) -> Optional[str]:
        if key in _memory_ttl and time.time() > _memory_ttl[key]:
            _memory_store.pop(key, None)
            _memory_ttl.pop(key, None)
            return None
        return _memory_store.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        _memory_store[key] = value
        if ex:
            _memory_ttl[key] = time.time() + ex

    async def setex(self, key: str, seconds: int, value: str):
        _memory_store[key] = value
        _memory_ttl[key] = time.time() + seconds

    async def delete(self, key: str):
        _memory_store.pop(key, None)
        _memory_ttl.pop(key, None)

    async def hgetall(self, key: str) -> Dict[str, str]:
        return _memory_hash.get(key, {})

    async def hset(self, key: str, mapping: Dict[str, str] = None, **kwargs):
        if key not in _memory_hash:
            _memory_hash[key] = {}
        if mapping:
            _memory_hash[key].update(mapping)

    async def hincrby(self, key: str, field: str, amount: int):
        if key not in _memory_hash:
            _memory_hash[key] = {}
        current = int(_memory_hash[key].get(field, "0"))
        _memory_hash[key][field] = str(current + amount)


async def get_redis():
    global _redis_pool, _fallback_mode

    if _fallback_mode:
        return _MemoryRedis()

    if _redis_pool is not None:
        return _redis_pool

    try:
        from sentinel.config import settings
        if not settings.redis_url:
            logger.info("Redis disabled (REDIS_URL empty) — using in-memory fallback")
            _fallback_mode = True
            return _MemoryRedis()

        import redis.asyncio as aioredis
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        # Test connection
        await _redis_pool.ping()
        logger.info("Redis connection pool created: %s", settings.redis_url)
        return _redis_pool
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — falling back to in-memory store", exc)
        _fallback_mode = True
        return _MemoryRedis()


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool and not _fallback_mode:
        await _redis_pool.aclose()
        _redis_pool = None


# ── Agent weight helpers ───────────────────────────────────────────────────────

WEIGHT_KEY_PREFIX = "sentinel:weights:"
_AGENT_COUNT = 15   # v3: 7 (v1) + 5 (v2) + 3 (v3)
DEFAULT_WEIGHT = 1.0 / _AGENT_COUNT  # uniform priors

# All 15 agents in the v3 mesh
_ALL_AGENTS = [
    # v1
    "InjectionScout", "PIISentinel", "JailbreakGuard",
    "ToxicityScreener", "HallucinationProbe", "ContextAnchor",
    "ComplianceTagger",
    # v2
    "ResponseSafetyLayer", "MultilingualGuard", "ToolCallSafety",
    "BrandGuard", "TokenAnomalyDetector",
    # v3
    "PromptLineage", "IntentClassifier", "AdversarialRephrasing",
]


async def get_agent_weights(tenant_id: str) -> dict[str, float]:
    """Load per-agent weights for a tenant from Redis hash."""
    redis = await get_redis()
    key = f"{WEIGHT_KEY_PREFIX}{tenant_id}"
    raw = await redis.hgetall(key)
    if not raw:
        # Initialise uniform weights for all 15 agents
        default = {a: str(DEFAULT_WEIGHT) for a in _ALL_AGENTS}
        await redis.hset(key, mapping=default)
        return {a: DEFAULT_WEIGHT for a in _ALL_AGENTS}
    # Ensure new agents get added if they're missing from an older store
    weights = {k: float(v) for k, v in raw.items()}
    missing = [a for a in _ALL_AGENTS if a not in weights]
    if missing:
        for a in missing:
            weights[a] = DEFAULT_WEIGHT
        await redis.hset(key, mapping={k: str(v) for k, v in weights.items()})
    return {k: float(v) for k, v in raw.items()}


async def update_agent_weight(tenant_id: str, agent_name: str,
                               delta: float) -> None:
    """
    Adjust a single agent's weight by delta (positive = more trusted,
    negative = less trusted after a human override).
    Weights are clamped to [0.01, 1.0] and renormalised.
    """
    redis = await get_redis()
    key = f"{WEIGHT_KEY_PREFIX}{tenant_id}"
    weights = await get_agent_weights(tenant_id)

    w = weights.get(agent_name, DEFAULT_WEIGHT)
    w = max(0.01, min(1.0, w + delta))
    weights[agent_name] = w

    # Renormalise so all weights sum to 1
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    await redis.hset(key, mapping={k: str(v) for k, v in weights.items()})
    logger.info("Weight updated: tenant=%s agent=%s new_weight=%.4f",
                tenant_id, agent_name, weights[agent_name])


# ── Dashboard counters ─────────────────────────────────────────────────────────

async def increment_decision_counter(tenant_id: str, decision: str) -> None:
    redis = await get_redis()
    await redis.hincrby(f"sentinel:stats:{tenant_id}:decisions", decision, 1)


async def get_decision_stats(tenant_id: str) -> dict:
    redis = await get_redis()
    raw = await redis.hgetall(f"sentinel:stats:{tenant_id}:decisions")
    return {k: int(v) for k, v in raw.items()}
