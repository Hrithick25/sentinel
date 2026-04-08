"""
SENTINEL Consensus — Risk Aggregator (formerly BayesianConsensus)
==================================================================
Aggregates per-agent scores into a single threat score using a
weighted ensemble voting model.

Enterprise framing: "If N of M agents flag this, block it."
Replaces the Bayesian terminology with clear, saleable language.

Weights are stored in Redis per-tenant and updated via human feedback:
  - Human marks a BLOCK as false positive → reduce weight of triggering agent
  - Human confirms a BLOCK was correct → increase weight

v4: Renamed from BayesianConsensus → RiskAggregator for clarity.
    Added veto-count logging, quorum check (3-of-N rule visible in metadata).
    Agent count bumped to 19 with new agents.
"""
from __future__ import annotations

import logging
from typing import Optional

from sentinel.models import AgentResult
from sentinel.storage.redis_client import get_agent_weights

logger = logging.getLogger("sentinel.consensus")

# Agents that are pure taggers or anomaly detectors — give near-zero threat weight
_STATIC_OVERRIDES = {
    "ComplianceTagger": 0.01,          # Pure tagger — no threat score
    "LocaleComplianceRouter": 0.05,    # Routing concern, lower weight
}

# Default fallback weight for unknown/new agents
_AGENT_COUNT = 19   # v4: 7 (v1) + 5 (v2) + 3 (v3) + 4 (v4 new agents)
_DEFAULT_WEIGHT = 1.0 / _AGENT_COUNT

# Quorum threshold: if >= N agents flag a request, escalate risk
_QUORUM_THRESHOLD = 3


class RiskAggregator:
    """
    Multi-Agent Consensus / Risk Aggregator.

    Runs weighted ensemble voting across all agents. If >= QUORUM_THRESHOLD
    agents flag the request, the minimum aggregate score is raised to 0.65
    (strong signal that something is wrong even if individual scores are low).
    """

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
        flagged_count = 0
        veto_count = 0

        for result in results:
            w = weights.get(result.agent_name, _DEFAULT_WEIGHT)
            weighted_sum += result.score * w
            used_weight += w
            if result.flagged:
                flagged_count += 1
            if getattr(result, "veto", False):
                veto_count += 1

        aggregate = weighted_sum / used_weight if used_weight > 0 else 0.0
        aggregate = max(0.0, min(1.0, aggregate))

        # Quorum override: 3+ agents flagging → floor at 0.65
        if flagged_count >= _QUORUM_THRESHOLD:
            aggregate = max(aggregate, 0.65)
            logger.info(
                "Quorum triggered: %d agents flagged — floor raised to 0.65",
                flagged_count,
            )

        logger.debug(
            "RiskAggregator: score=%.4f | agents=%d | flagged=%d | vetoes=%d | agent_scores=%s",
            aggregate,
            len(results),
            flagged_count,
            veto_count,
            {r.agent_name: round(r.score, 3) for r in results},
        )

        return aggregate, weights


# Backwards-compatibility alias — old code that imports BayesianConsensus still works
BayesianConsensus = RiskAggregator
