"""
SENTINEL — Human Feedback Loop
==================================
Implements the adaptive weight update mechanism:
  1. Security team reviews a BLOCK decision
  2. If it's a false positive → reduce triggering agent weight
  3. If it's confirmed → increase triggering agent weight
  4. Weights auto-normalise so the system learns over time

This is the self-improving loop that makes SENTINEL better
with every human review — the Bayesian feedback flywheel.
"""
from __future__ import annotations

import logging
from pydantic import BaseModel
from enum import Enum
from typing import Optional

from sentinel.storage.redis_client import update_agent_weight, get_agent_weights

logger = logging.getLogger("sentinel.feedback")

WEIGHT_ADJUST = 0.02  # ~2% shift per feedback event


class FeedbackVerdict(str, Enum):
    FALSE_POSITIVE = "false_positive"   # was flagged but shouldn't have been
    CONFIRMED      = "confirmed"        # flag was correct
    FALSE_NEGATIVE = "false_negative"   # wasn't flagged but should have been


class FeedbackRequest(BaseModel):
    audit_id: str
    verdict: FeedbackVerdict
    agent_name: Optional[str] = None   # if null, all agents are adjusted
    notes: Optional[str] = None


async def process_feedback(
    tenant_id: str,
    feedback: FeedbackRequest,
) -> dict:
    """
    Adjust agent weights based on human feedback.
    Returns the new weight state.
    """
    if feedback.verdict == FeedbackVerdict.FALSE_POSITIVE:
        # The agent was wrong — reduce its weight
        if feedback.agent_name:
            await update_agent_weight(tenant_id, feedback.agent_name, -WEIGHT_ADJUST)
            logger.info(
                "FP feedback: tenant=%s agent=%s weight decreased",
                tenant_id, feedback.agent_name,
            )
        else:
            logger.info("FP feedback without agent — skipped weight update")

    elif feedback.verdict == FeedbackVerdict.CONFIRMED:
        # The agent was right — increase its weight
        if feedback.agent_name:
            await update_agent_weight(tenant_id, feedback.agent_name, +WEIGHT_ADJUST)
            logger.info(
                "Confirmed feedback: tenant=%s agent=%s weight increased",
                tenant_id, feedback.agent_name,
            )

    elif feedback.verdict == FeedbackVerdict.FALSE_NEGATIVE:
        # Something was missed — boost all detection agents slightly
        detection_agents = [
            # v1
            "InjectionScout", "PIISentinel", "JailbreakGuard",
            "ToxicityScreener", "HallucinationProbe",
            # v2
            "ResponseSafetyLayer", "MultilingualGuard", "ToolCallSafety",
            "BrandGuard", "TokenAnomalyDetector",
            # v3
            "IntentClassifier", "AdversarialRephrasing",
        ]
        for agent in detection_agents:
            await update_agent_weight(tenant_id, agent, +WEIGHT_ADJUST * 0.5)
        logger.info(
            "False negative feedback: all detection agents boosted for tenant=%s",
            tenant_id,
        )

    weights = await get_agent_weights(tenant_id)
    return {
        "status": "processed",
        "verdict": feedback.verdict,
        "new_weights": {k: round(v, 4) for k, v in weights.items()},
    }
