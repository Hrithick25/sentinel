"""
SENTINEL Consensus — Circuit Breaker
========================================
Three-level decision gate based on aggregate threat score and tenant policy:

  score < lower_threshold  →  ALLOW   (pass through to LLM unchanged)
  lower ≤ score < upper    →  REWRITE (sanitize and retry with cleaned prompt)
  score ≥ upper_threshold  →  BLOCK   (reject; embed in FAISS for future detection)

Also identifies the triggering agent (highest individual score among flagged agents).
"""
from __future__ import annotations

import logging
from typing import Optional

from sentinel.models import AgentResult, Decision, TenantPolicy

logger = logging.getLogger("sentinel.circuit_breaker")


class CircuitBreaker:

    def decide(
        self,
        score: float,
        results: list[AgentResult],
        policy: TenantPolicy,
    ) -> tuple[Decision, Optional[str]]:
        """
        Returns (decision, triggering_agent_name).
        triggering_agent is the highest-scoring FLAGGED agent (or None on ALLOW).
        """
        # Identify triggering agent
        flagged = [r for r in results if r.flagged]
        triggering_agent: Optional[str] = None
        if flagged:
            triggering_agent = max(flagged, key=lambda r: r.score).agent_name

        if score >= policy.upper_threshold:
            decision = Decision.BLOCK
            logger.warning(
                "🔴 BLOCK | score=%.4f | trigger=%s | tenant=%s",
                score, triggering_agent, policy.tenant_id,
            )

        elif score >= policy.lower_threshold:
            decision = Decision.REWRITE if policy.allow_rewrite else Decision.BLOCK
            logger.info(
                "🟡 %s | score=%.4f | trigger=%s | tenant=%s",
                decision, score, triggering_agent, policy.tenant_id,
            )

        else:
            decision = Decision.ALLOW
            triggering_agent = None
            logger.info(
                "🟢 ALLOW | score=%.4f | tenant=%s",
                score, policy.tenant_id,
            )

        return decision, triggering_agent
