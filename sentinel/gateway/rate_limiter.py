"""
SENTINEL — Rate Limiter
=========================
Sliding-window rate limiter backed by Redis.
Supports per-tenant and per-plan limits.

Plan limits (requests per minute):
  free:       30
  pro:       300
  enterprise: Unlimited (10000 as practical cap)
"""
from __future__ import annotations

import logging
import time
from typing import Optional
from fastapi import HTTPException

from sentinel.storage.redis_client import get_redis

logger = logging.getLogger("sentinel.rate_limiter")

PLAN_LIMITS = {
    "free":       30,
    "pro":        300,
    "enterprise": 10000,
}

RATE_KEY = "sentinel:rate:{tenant_id}"
WINDOW = 60  # seconds


async def check_rate_limit(tenant_id: str, plan: str = "free") -> dict:
    """
    Sliding-window rate check.
    Returns { allowed: bool, remaining: int, reset_at: float }
    Raises HTTPException 429 on limit breach.
    """
    redis = await get_redis()
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    key = RATE_KEY.format(tenant_id=tenant_id)
    now = time.time()
    window_start = now - WINDOW

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, WINDOW + 1)
    results = await pipe.execute()

    count = results[2]
    remaining = max(0, limit - count)

    if count > limit:
        reset_at = window_start + WINDOW
        logger.warning(
            "Rate limit exceeded: tenant=%s plan=%s count=%d limit=%d",
            tenant_id, plan, count, limit,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "limit": limit,
                "window": f"{WINDOW}s",
                "retry_after": round(reset_at - now, 1),
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(int(reset_at - now) + 1),
            },
        )

    return {"allowed": True, "remaining": remaining, "limit": limit}


async def get_usage_stats(tenant_id: str) -> dict:
    """Return current-window usage for dashboard display."""
    redis = await get_redis()
    key = RATE_KEY.format(tenant_id=tenant_id)
    now = time.time()
    count = await redis.zcount(key, now - WINDOW, now)
    return {"current_window_count": count, "window_seconds": WINDOW}
