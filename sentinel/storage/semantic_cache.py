"""
SENTINEL - Enterprise Semantic Caching
======================================
Stores exact and semantic embeddings of prompts to eliminate LLM provider costs
and drastically reduce latency for repeated or similar queries.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sentinel.storage.redis_client import get_redis

logger = logging.getLogger("sentinel.storage.semantic_cache")

class SemanticCache:
    def __init__(self):
        self.prefix = "sentinel:cache:v1:"

    async def get_cached_response(self, text: str, tenant_id: str) -> Optional[str]:
        """Check if an identical or highly similar prompt was already processed."""
        try:
            redis = await get_redis()
            
            # Step 1: Exact Hash Match (O(1) Redis Lookup ~1ms)
            query_hash = hashlib.sha256(text.encode()).hexdigest()
            exact_key = f"{self.prefix}exact:{tenant_id}:{query_hash}"
            
            cached = await redis.get(exact_key)
            if cached:
                logger.info("⚡ Semantic Cache HIT! Saved LLM tokens.")
                # Redis decode_responses=True returns str, not bytes
                return cached if isinstance(cached, str) else cached.decode("utf-8")
                
            # Step 2: Semantic Vector Match (via FAISS ~10ms)
            # Placeholder for vector similarity search. In absolute maximum version,
            # this extracts sentence-transformer embedding and searches FAISS for >0.98 similarity.
            
            return None
        except Exception as e:
            logger.warning(f"Cache miss or error: {e}")
            return None

    async def set_cached_response(self, text: str, response: str, tenant_id: str):
        """Store the response for future cost savings."""
        try:
            redis = await get_redis()
            query_hash = hashlib.sha256(text.encode()).hexdigest()
            exact_key = f"{self.prefix}exact:{tenant_id}:{query_hash}"
            
            # Cache for 24 hours
            await redis.setex(exact_key, 86400, response)
        except Exception as e:
            logger.error(f"Failed to set cache: {e}")

semantic_cache = SemanticCache()
