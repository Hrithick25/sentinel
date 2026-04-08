"""
SENTINEL Agent v4 — CostAnomalyDetector
==========================================
Detects runaway token usage — a real, underappreciated enterprise concern.

Enterprise use case:
  - A prompt that triggers a 100k-token response costs $3+ per call
  - A compromised or misconfigured chatbot can burn $10k/day in token spend
  - This agent fires when token spend spikes 3x above baseline
  - Works alongside TokenAnomalyDetector (which detects token stuffing in prompts)

What this agent detects:
  1. Unusually large max_tokens requests (prompt fishing)
  2. Requests designed to elicit very long responses ("give me a list of 10,000...")
  3. Repetitive/loop-triggering prompts that could cause runaway generation
  4. Tenant spend-rate anomalies (via sliding window, Redis-backed)
  5. Prompt patterns that correlate with high token output

Differs from TokenAnomalyDetector:
  - TokenAnomalyDetector: detects token stuffing / context window attacks (INPUT side)
  - CostAnomalyDetector: detects patterns that cause runaway LLM OUTPUT costs
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from sentinel.agents.base import SentinelAgent
from sentinel.models import AgentResult, SentinelRequest

logger = logging.getLogger("sentinel.agents.cost_anomaly_detector")

# ── Patterns that correlate with high-cost responses ─────────────────────────
_COST_PATTERNS = [
    # Requesting very long lists or exhaustive output
    r"(list|generate|write|give\s+me|create|produce)\s+(all|every|each|10[,\s]?000|1000|100[,\s]?000)",
    r"(give|write|generate|list)\s+(me\s+)?\d{4,}",
    r"(complete|full|entire|exhaustive|comprehensive)\s+(list|database|encyclopedia|guide)",
    r"(every\s+(possible|single)|all\s+possible)\s+(word|combination|permutation|example|case)",

    # Repeat/loop triggers
    r"(repeat|say|write|print|output)\s+(this|the\s+following|it)\s+\d+\s+times",
    r"(loop|iterate|repeat).{0,20}\d+\s+times",
    r"keep\s+(going|writing|generating|producing)\s+(until|for\s+\d+)",

    # Prompts fishing for system-level verbosity
    r"(explain|describe|list|enumerate)\s+every\s+(step|detail|option|possible|thing)",
    r"do\s+not\s+(stop|end|finish|truncate|limit)",
    r"(continue\s+until|keep\s+(writing|going)\s+until)",
    r"write\s+(as\s+much|as\s+long)\s+as\s+(possible|you\s+can)",
    r"no\s+(word\s+)?limit",

    # Inference bomb patterns
    r"(translate|convert|transform)\s+the\s+(entire|full|complete|whole)\s+(bible|quran|wikipedia|book)",
    r"summarize\s+(every|all)\s+\d+\s+(chapters?|pages?|sections?|articles?)",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _COST_PATTERNS]

# High max_tokens is itself a signal
_HIGH_TOKENS_THRESHOLD = 4000
_EXTREME_TOKENS_THRESHOLD = 8000


class CostAnomalyDetector(SentinelAgent):
    """
    Detects patterns that could trigger runaway LLM token costs.
    Fires when spend patterns spike 3x above tenant baseline (Redis-backed)
    or when prompt patterns correlate with extremely high output tokens.
    """
    agent_name = "CostAnomalyDetector"

    async def analyze(self, request: SentinelRequest) -> AgentResult:
        text = request.last_user_message
        max_tokens = request.max_tokens

        # ── 1. Check requested max_tokens ───────────────────────────────────
        token_score = 0.0
        if max_tokens >= _EXTREME_TOKENS_THRESHOLD:
            token_score = 0.70
        elif max_tokens >= _HIGH_TOKENS_THRESHOLD:
            token_score = 0.40

        # ── 2. Pattern matching for cost-trigger prompts ─────────────────────
        hits = [p.pattern for p in _COMPILED if p.search(text)]
        pattern_score = self._clamp(len(hits) * 0.30)

        # ── 3. Check tenant spend rate (Redis-backed sliding window) ─────────
        spend_score = await self._check_tenant_spend_rate(request.tenant_id)

        # ── 4. Composite score ───────────────────────────────────────────────
        score = self._clamp(max(token_score, pattern_score, spend_score))
        flagged = score >= 0.55

        return AgentResult(
            agent_name=self.agent_name,
            score=score,
            flagged=flagged,
            metadata={
                "max_tokens_requested": max_tokens,
                "token_score": round(token_score, 4),
                "cost_pattern_hits": hits[:5],
                "pattern_score": round(pattern_score, 4),
                "spend_rate_score": round(spend_score, 4),
            },
        )

    async def _check_tenant_spend_rate(self, tenant_id: str) -> float:
        """
        Check if this tenant's token usage has spiked recently.
        Returns 0.0 if Redis is unavailable (graceful degradation).
        """
        try:
            from sentinel.storage.redis_client import get_redis
            redis = await get_redis()
            if redis is None:
                return 0.0

            key = f"sentinel:spend:{tenant_id}"
            # Increment and get current sliding-window count
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, 300)  # 5-minute window

            # Get baseline (stored separately, updated hourly)
            baseline_key = f"sentinel:spend_baseline:{tenant_id}"
            baseline_raw = await redis.get(baseline_key)
            baseline = float(baseline_raw) if baseline_raw else None

            if baseline is None or baseline == 0:
                # Not enough history — update baseline and return clean
                await redis.set(baseline_key, max(current, 1), ex=3600)
                return 0.0

            spike_ratio = current / baseline
            if spike_ratio >= 5.0:
                return 0.85
            elif spike_ratio >= 3.0:
                return 0.60
            elif spike_ratio >= 2.0:
                return 0.30
            return 0.0

        except Exception as exc:
            logger.debug("Cost spend check skipped: %s", exc)
            return 0.0
