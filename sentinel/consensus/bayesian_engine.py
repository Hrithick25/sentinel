"""
SENTINEL Consensus — Bayesian Engine
========================================
Aggregates per-agent scores into a single threat score using a
weighted Bayesian model.

Weights are stored in Redis per-tenant and updated via human feedback:
  - Human marks a BLOCK as false positive → reduce weight of triggering agent
  - Human confirms a BLOCK was correct → increase weight

v2: Updated from 7 to 12 agents. Starting weights are uniform (1/N).
    BrandGuard and TokenAnomalyDetector are taggers/anomaly detectors
    with lower base weights.
"""
from __future__ import annotations

import logging
from typing import Optional

from sentinel.models import AgentResult
from sentinel.storage.redis_client import get_agent_weights

logger = logging.getLogger("sentinel.consensus")

# Agents that are pure taggers or anomaly detectors — give near-zero threat weight
_STATIC_OVERRIDES = {
    "ComplianceTagger": 0.01,       # Pure tagger — no threat score
}

# Default fallback weight for unknown/new agents
_AGENT_COUNT = 15   # v3: 7 (v1) + 5 (v2) + 3 (v3)
_DEFAULT_WEIGHT = 1.0 / _AGENT_COUNT


class BayesianConsensus:

    async def aggregate(
        self,
        results: list[AgentResult],
        tenant_id: str,
    ) -> tuple[float, dict[str, float]]:
        """
        Returns:
          aggregate_score : float in [0, 1]
          weights         : dict[agent_name → effective_weight]  (for audit trail)
        """
        # Load per-tenant weights from Redis
        weights = await get_agent_weights(tenant_id)

        # Apply static overrides (ComplianceTagger etc.)
        for agent, override_w in _STATIC_OVERRIDES.items():
            if agent in weights:
                weights[agent] = override_w

        # Normalise weights (they may have drifted after many feedback updates)
        total_w = sum(weights.values())
        if total_w > 0:
            weights = {k: v / total_w for k, v in weights.items()}

        # Weighted average
        weighted_sum = 0.0
        used_weight = 0.0
        for result in results:
            w = weights.get(result.agent_name, _DEFAULT_WEIGHT)
            weighted_sum += result.score * w
            used_weight += w

        aggregate = weighted_sum / used_weight if used_weight > 0 else 0.0
        aggregate = max(0.0, min(1.0, aggregate))

        logger.debug(
            "Consensus: score=%.4f | agents=%d | agent_scores=%s",
            aggregate,
            len(results),
            {r.agent_name: round(r.score, 3) for r in results},
        )

        return aggregate, weights
